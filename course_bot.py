import boto3
import json

class CourseBot:
    def __init__(self, course_id):
        self.course_id = course_id
        self.s3 = boto3.client('s3')
        self.bedrock = boto3.client('bedrock')
        self.bedrock_agent = boto3.client('bedrock-agent')
        self.iam = boto3.client('iam')
        self.opensearch = boto3.client('opensearch')

    def create_s3_bucket(self):
        bucket_name = f"course-{self.course_id}"
        response = self.s3.create_bucket(Bucket=bucket_name)
        return response
    
    def sync_content(self, file_content):
        bucket_name = f"course-{self.course_id}"
        object_key = f"text_files/{self.course_id}-content.html"
        response = self.s3.put_object(Body=file_content, Bucket=bucket_name, Key=object_key)
        return response
    
    def create_kb_arn(self):
        # Define the trust relationship
        trust_relationship = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"  # Assuming Lambda needs the role
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        # Define a policy with the necessary permissions for Bedrock knowledge base
        # This is a placeholder; you need to specify actual permissions
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "bedrock:*",  # Assuming 'bedrock' is the prefix for the service's permissions
                    "Resource": "*"  # This gives access to all Bedrock resources, which may not be best practice
                }
            ]
        }
        role_response = self.iam.create_role(
            RoleName='BedrockKnowledgeBaseAccessRole',
            AssumeRolePolicyDocument=json.dumps(trust_relationship)
        )
        
         # Create the policy
        policy_response = self.iam.create_policy(
            PolicyName='BedrockKnowledgeBaseFullAccess',
            PolicyDocument=json.dumps(policy_document)
        )
        
        return role_response['Role']['Arn']

    def create_os_collection(self):
        collection = self.opensearch.create_serverless_collection(
            DomainName='dora-profuturo',
            CollectionName=f"course-{self.course_id}",
        )
        arn = collection['createCollectionDetail']['arn']
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "aoss:UpdateLifecyclePolicy"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "aoss:collection": "application-logs"
                        }
                    }
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "aoss:ListLifecyclePolicies",
                        "aoss:BatchGetLifecyclePolicy"
                    ],
                    "Resource": "*"
                }
            ]
        }
        response = self.opensearch.create_lifecycle_policy(
            name=f"course-{self.course_id}-lifecycle-policy",
            policy=json.dump(policy),
            type='retention'
        )
        
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "aoss:UpdateSecurityPolicy"
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "aoss:collection": "application-logs"
                        }
                    }
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "aoss:ListSecurityPolicies",
                        "aoss:GetSecurityPolicy"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        response = self.opensearch.create_security_policy(
            name=f"course-{self.course_id}-network-policy",
            policy=json.dump(policy),
            type='network'
        )
        
        return collection['createCollectionDetail']['arn']
                   
    def create_knowledge_base(self):
        response = self.bedrock_agent.create_knowledge_base(
            name=f"course-{self.course_id}",
            description=f"course-{self.course_id}",
            roleArn=self.create_kb_arn(),
            knowledgeBaseConfiguration={
                'type': 'VECTOR',
                'vectorKnowledgeBaseConfiguration': {
                    'embeddingModelArn': 'arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1'
                }
            },
            storageConfiguration={
                'type': 'OPENSEARCH_SERVERLESS',
                'opensearchServerlessConfiguration': {
                    'collectionArn': self.create_os_collection(),
                    'vectorIndexName': 'string',
                    'fieldMapping': {
                        'vectorField': 'string',
                        'textField': 'string',
                        'metadataField': 'string'
                    }
                }
            }
        )
        return response
    
    def create_data_source(self):
        response = self.bedrock_agent.create_data_source(
            knowledgeBaseId=,
            name=f"course-{self.course_id}",
            description=f"course-{self.course_id}",
            dataSourceConfiguration={
                'type': 'S3',
                's3Configuration': {
                    'bucketArn': f"arn:aws:s3:::course-{self.course_id}"
                }
            },
            serverSideEncryptionConfiguration={
                'kmsKeyArn': 'arn:aws:kms:us-east-1:066864718477:key/0b7339b4-2ae9-4502-a9be-772c2a736be1'
            },
            vectorIngestionConfiguration={
                'chunkingConfiguration': {
                    'chunkingStrategy': 'FIXED_SIZE',
                    'fixedSizeChunkingConfiguration': {
                        'maxTokens': 123,
                        'overlapPercentage': 25
                    }
                }
            }
        )
        return response

    def create_agent(self):
        response = self.bedrock_agent.create_agent(
            name=f"{self.course_id}-agent",
            roleArn='arn:aws:iam::123456789012:role/service-role/AmazonBedrockExecutionRoleForAgent',
            agentConfiguration={
                'type': 'TEXT',
                'textAgentConfiguration': {
                    'knowledgeBaseArn': 'arn:aws:bedrock:us-east-1:123456789012:knowledge-base/course-knowledge-base'
                }
            }
        )
        return response