import asyncio
import io
import json
import logging
import random
import re
import string
import sys
import uuid
import yaml
import zipfile
import time
import os
import boto3
from botocore.exceptions import ClientError

from bedrock_agent_wrapper import BedrockAgentWrapper

logger = logging.getLogger(__name__)

REGION = "us-east-1"
ROLE_POLICY_NAME = "agent_permissions"
LAMBDA_FUNCTIONS = [
        {
            "name": "CourseGrades",
            "description": "Get the grades of the students in the course.",
        },
        {
            "name": "CourseEvents",
            "description": "Get the events in the course.", 
        }
    ]

class BotClient:
    def __init__(
        self, bedrock_agent_client, runtime_client, lambda_client, iam_resource, postfix
    ):
        self.iam_resource = iam_resource
        self.lambda_client = lambda_client
        self.bedrock_agent_runtime_client = runtime_client
        self.postfix = postfix

        self.bedrock_wrapper = BedrockAgentWrapper(bedrock_agent_client)

        self.agent = None
        self.agent_alias = None
        self.agent_role = None
        self.prepared_agent_details = None
        self.lambda_roles = {}
        self.lambda_functions = {}
        for function in LAMBDA_FUNCTIONS:
            self.lambda_roles[function['name']] = None
            self.lambda_functions[function['name']] = None

    def create_course_bot(self, course_id):
        name = f"course_bot_{course_id}"
        foundation_model = "anthropic.claude-v2"
        
        self.course_id = course_id

        # Create an execution role for the agent
        self.agent_role = self._create_agent_role(foundation_model)

        # Create the agent
        self.agent = self._create_agent(name, foundation_model)

        # Prepare a DRAFT version of the agent
        self.prepared_agent_details = self._prepare_agent()
        
        for function in LAMBDA_FUNCTIONS:
            # Create the agent's Lambda function
            self.lambda_functions[function['name']] = self._create_lambda_function(function["name"])

            # Configure permissions for the agent to invoke the Lambda function
            self._allow_agent_to_invoke_function(function["name"])
            self._let_function_accept_invocations_from_agent(function["name"])

            # Create an action group to connect the agent with the Lambda function
            self._create_agent_action_group(function["name"])

        # If the agent has been modified or any components have been added, prepare the agent again
        components = [self._get_agent()]
        components += self._get_agent_action_groups()
        components += self._get_agent_knowledge_bases()

        latest_update = max(component["updatedAt"] for component in components)
        if latest_update > self.prepared_agent_details["preparedAt"]:
            self.prepared_agent_details = self._prepare_agent()

        # Create an agent alias
        self.agent_alias = self._create_agent_alias()
        
        print('passei')
        
        return self.to_dict()
    
    def to_dict(self):
        response = {
            "agent_role": self.agent_role.role_name,
            "agent_id": self.agent["agentId"],
            "agent_alias": self.agent_alias["agentAliasId"],
            "lambda": {
                "functions": {},
                "roles": {}
                },
        }
        print(response)
        for function in LAMBDA_FUNCTIONS:
            response['lambda']['functions'][function['name']] = self.lambda_functions[function["name"]]["FunctionName"]
            response['lambda']['roles'][function['name']] = self.lambda_roles[function["name"]].role_name
        return response
    
    def _create_agent_role(self, model_id):
        role_name = f"AmazonBedrockExecutionRoleForAgents_{self.postfix}_{self.course_id}"
        
        model_arn = f"arn:aws:bedrock:{REGION}::foundation-model/{model_id}*"

        print("Creating an an execution role for the agent...")

        try:
            role = self.iam_resource.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "bedrock.amazonaws.com"},
                                "Action": "sts:AssumeRole",
                            }
                        ],
                    }
                ),
            )

            role.Policy(ROLE_POLICY_NAME).put(
                PolicyDocument=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": "bedrock:InvokeModel",
                                "Resource": model_arn,
                            }
                        ],
                    }
                )
            )
        except ClientError as e:
            logger.error(f"Couldn't create role {role_name}. Here's why: {e}")
            raise

        return role

    def _create_agent(self, name, model_id):
        print("Creating the agent...")

        instruction = """
            Your name is Dora. You act as a pedagogical assistant in a course on the Profuturo platform, providing help based on the files uploaded and functions available. 
            Be gentle and polite, but keep anwsers concise, and answer in steps. Ommit the answer sources.
            """
        agent = self.bedrock_wrapper.create_agent(
            agent_name=name,
            foundation_model=model_id,
            instruction=instruction,
            role_arn=self.agent_role.arn
        )
        self._wait_for_agent_status(agent["agentId"], "NOT_PREPARED")

        return agent
    
    

    def _prepare_agent(self):
        print("Preparing the agent...")

        agent_id = self.agent["agentId"]
        prepared_agent_details = self.bedrock_wrapper.prepare_agent(agent_id)
        self._wait_for_agent_status(agent_id, "PREPARED")

        return prepared_agent_details

    def _create_lambda_function(self, function_name):
        print("Creating the Lambda function...")

        function = f"AmazonBedrockExampleFunction_{self.postfix}_{self.course_id}_{function_name}"

        self.lambda_roles[function_name] = self._create_lambda_roles(function_name)

        try:
            deployment_package = self._create_deployment_package(function_name)

            lambda_function = self.lambda_client.create_function(
                FunctionName=function,
                Description="Lambda function for Amazon Bedrock example",
                Runtime="python3.11",
                Role=self.lambda_roles[function_name].arn,
                Handler=f"{function}.lambda_handler",
                Code={"ZipFile": deployment_package},
                Publish=True,
            )

            waiter = self.lambda_client.get_waiter("function_active_v2")
            waiter.wait(FunctionName=function)

        except ClientError as e:
            logger.error(
                f"Couldn't create Lambda function {function}. Here's why: {e}"
            )
            raise

        return lambda_function

    def _create_lambda_roles(self, function_name):
        print("Creating an execution role for the Lambda function...")

        role_name = f"AmazonBedrockExecutionRoleForLambda_{self.postfix}_{self.course_id}_{function_name}"

        try:
            role = self.iam_resource.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "lambda.amazonaws.com"},
                                "Action": "sts:AssumeRole",
                            }
                        ],
                    }
                ),
            )
            role.attach_policy(
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            )
            print(f"Created role {role_name}")
        except ClientError as e:
            logger.error(f"Couldn't create role {role_name}. Here's why: {e}")
            raise

        print("Waiting for the execution role to be fully propagated...")
        time.sleep(10)

        return role

    def _allow_agent_to_invoke_function(self, function_name):
        policy = self.iam_resource.RolePolicy(
            self.agent_role.role_name, ROLE_POLICY_NAME
        )
        doc = policy.policy_document
        doc["Statement"].append(
            {
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": self.lambda_functions[function_name]["FunctionArn"],
            }
        )
        self.agent_role.Policy(ROLE_POLICY_NAME).put(PolicyDocument=json.dumps(doc))

    def _let_function_accept_invocations_from_agent(self, function_name):
        try:
            self.lambda_client.add_permission(
                FunctionName=self.lambda_functions[function_name]["FunctionName"],
                SourceArn=self.agent["agentArn"],
                StatementId="BedrockAccess",
                Action="lambda:InvokeFunction",
                Principal="bedrock.amazonaws.com",
            )
        except ClientError as e:
            logger.error(
                f"Couldn't grant Bedrock permission to invoke the Lambda function. Here's why: {e}"
            )
            raise

    def _create_agent_action_group(self, function_name):
        print("Creating an action group for the agent...")

        try:
            self.bedrock_wrapper.create_agent_action_group(
                name=f"{function_name}",
                description="Gets the current date and time.",
                agent_id=self.agent["agentId"],
                agent_version=self.prepared_agent_details["agentVersion"],
                function_arn=self.lambda_functions[function_name]["FunctionArn"],
                api_schema=json.dumps(yaml.safe_load(open(f'./lambda/{function_name}.yaml').read())),
            )
        except ClientError as e:
            logger.error(f"Couldn't create agent action group. Here's why: {e}")
            raise

    def _get_agent(self):
        return self.bedrock_wrapper.get_agent(self.agent["agentId"])

    def _get_agent_action_groups(self):
        return self.bedrock_wrapper.list_agent_action_groups(
            self.agent["agentId"], self.prepared_agent_details["agentVersion"]
        )

    def _get_agent_knowledge_bases(self):
        return self.bedrock_wrapper.list_agent_knowledge_bases(
            self.agent["agentId"], self.prepared_agent_details["agentVersion"]
        )

    def _create_agent_alias(self):
        print("Creating an agent alias...")

        agent_alias_name = "test_agent_alias"
        agent_alias = self.bedrock_wrapper.create_agent_alias(
            agent_alias_name, self.agent["agentId"]
        )

        self._wait_for_agent_status(self.agent["agentId"], "PREPARED")

        return agent_alias

    def _wait_for_agent_status(self, agent_id, status):
        while self.bedrock_wrapper.get_agent(agent_id)["agentStatus"] != status:
            time.sleep(2)

    def _chat_with_agent(self, agent_alias, prompt): 
        print("-" * 88)
        print("The agent is ready to chat.")
        print("Try asking for the date or time. Type 'exit' to quit.")

        # Create a unique session ID for the conversation
        response = asyncio.run(self._invoke_agent(agent_alias, prompt ))

        print(f"Agent: {response}")

    async def _invoke_agent(self, agent_alias, prompt, session_id):
        response = self.bedrock_agent_runtime_client.invoke_agent(
            agentId=self.agent["agentId"],
            agentAliasId=agent_alias["agentAliasId"],
            sessionId=session_id,
            inputText=prompt,
        )

        completion = ""

        for event in response.get("completion"):
            chunk = event["chunk"]
            completion += chunk["bytes"].decode()

        return completion

    def _delete_resources(self):
        if self.agent:
            agent_id = self.agent["agentId"]

            if self.agent_alias:
                agent_alias_id = self.agent_alias["agentAliasId"]
                print("Deleting agent alias...")
                self.bedrock_wrapper.delete_agent_alias(agent_id, agent_alias_id)

            print("Deleting agent...")
            agent_status = self.bedrock_wrapper.delete_agent(agent_id)["agentStatus"]
            while agent_status == "DELETING":
                time.sleep(5)
                try:
                    agent_status = self.bedrock_wrapper.get_agent(
                        agent_id, log_error=False
                    )["agentStatus"]
                except ClientError as err:
                    if err.response["Error"]["Code"] == "ResourceNotFoundException":
                        agent_status = "DELETED"

        if self.lambda_functions:
            for function in self.lambda_functions:
                name = function["FunctionName"]
                print(f"Deleting function '{name}'...")
                self.lambda_client.delete_function(FunctionName=name)

        if self.agent_role:
            print(f"Deleting role '{self.agent_role.role_name}'...")
            self.agent_role.Policy(ROLE_POLICY_NAME).delete()
            self.agent_role.delete()

        if self.lambda_roles:
            for role in self.lambda_roles:
                print(f"Deleting role '{role.role_name}'...")
                for policy in role.attached_policies.all():
                    policy.detach_role(RoleName=role.role_name)
                self.lambda_roles.delete()

    def _list_resources(self):
        print("-" * 40)
        print(f"Here is the list of created resources in '{REGION}'.")
        print("Make sure you delete them once you're done to avoid unnecessary costs.")
        if self.agent:
            print(f"Bedrock Agent:   {self.agent['agentName']}")
        if self.lambda_function:
            print(f"Lambda function: {self.lambda_function['FunctionName']}")
        if self.agent_role:
            print(f"IAM role:        {self.agent_role.role_name}")
        if self.lambda_roles:
            print(f"IAM role:        {self.lambda_roles.role_name}")

    @staticmethod
    def is_valid_agent_name(answer):
        valid_regex = r"^[a-zA-Z0-9_-]{1,100}$"
        return (
            answer
            if answer and len(answer) <= 100 and re.match(valid_regex, answer)
            else None,
            "I need a name for the agent, please. Valid characters are a-z, A-Z, 0-9, _ (underscore) and - (hyphen).",
        )

    @staticmethod
    def _create_deployment_package(function_name):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            for folderName, subfolders, filenames in os.walk(f'./lambda'):
                for filename in filenames:
                    filePath = os.path.join(folderName, filename)
                    zipped.write(filePath, os.path.relpath(filePath, f'./lambda/lib'))

        buffer.seek(0)
        return buffer.read()