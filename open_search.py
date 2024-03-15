from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3
import botocore
import time
import os

# Build the client using the default credential configuration.
# You can use the CLI and run 'aws configure' to set access key, secret
# key, and default region.

class OpenSearchServerless:
    def __init__(self, course_id):
            self.course_id = course_id
            self.client = boto3.client(
                service_name='opensearchserverless',
                region_name='us-east-1',
                aws_access_key_id=os.environ['ACCESS_KEY'],
                aws_secret_access_key=os.environ['SECRET_KEY']
            )

    def createEncryptionPolicy(self):
        """Creates an encryption policy that matches all collections beginning with tv-"""
        try:
            response = self.client.create_security_policy(
                name=f"course-{self.course_id}-encryption-policy",
                policy=f"""
                    {
                        "Rules":[
                            {
                                "ResourceType":"collection",
                                "Resource":[
                                    "collection/course-{self.course_id}-*"
                                ]
                            }
                        ],
                        "AWSOwnedKey":true
                    }
                    """,
                type='encryption'
            )
            print(response)
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'ConflictException':
                print(
                    '[ConflictException] The policy name or rules conflict with an existing policy.')
            else:
                raise error


    def createNetworkPolicy(self):
        """Creates a network policy that matches all collections beginning with tv-"""
        try:
            response = self.client.create_security_policy(
                name=f"course-{self.course_id}-network-policy",
                policy=f"""
                    [{
                        "Rules":[
                            {
                                "ResourceType":"dashboard",
                                "Resource":["collection/course-{self.course_id}-*"]
                            },
                            {
                                "ResourceType":"collection",
                                "Resource":["collection/course-{self.course_id}-*"]
                            }
                        ],
                        "AllowFromPublic":True
                    }]
                    """,
                type='network'
            )
            print('\nNetwork policy created:')
            print(response)
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'ConflictException':
                print(
                    '[ConflictException] A network policy with this name already exists.')
            else:
                raise error


    def createAccessPolicy(self):
        """Creates a data access policy that matches all collections beginning with tv-"""
        try:
            response = self.client.create_access_policy(
                name=f"course-{self.course_id}-access-policy",
                policy=f"""
                    [{
                        "Rules":[
                            {
                                "Resource":[
                                    "index/course-{self.course_id}-/*"
                                ],
                                "Permission":[
                                    "aoss:CreateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument"
                                ],
                                "ResourceType": "index"
                            },
                            {
                                "Resource":[
                                    "index/course-{self.course_id}-/*"
                                ],
                                "Permission":[
                                    "aoss:CreateCollectionItems"
                                ],
                                "ResourceType": "collection"
                            }
                        ],
                        "Principal":[
                            "arn:aws:iam::066864718477:role\/Admin"
                        ]
                    }]
                    """,
                type='data'
            )
            print('\nAccess policy created:')
            print(response)
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'ConflictException':
                print(
                    '[ConflictException] An access policy with this name already exists.')
            else:
                raise error


    def createCollection(self):
        """Creates a collection"""
        try:
            response = self.client.create_collection(
                name=f"course-{self.course_id}",
                type='SEARCH'
            )
            return(response)
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'ConflictException':
                print(
                    '[ConflictException] A collection with this name already exists. Try another name.')
            else:
                raise error


    def waitForCollectionCreation(client):
        """Waits for the collection to become active"""
        response = client.batch_get_collection(
            names=['tv-sitcoms'])
        # Periodically check collection status
        while (response['collectionDetails'][0]['status']) == 'CREATING':
            print('Creating collection...')
            time.sleep(30)
            response = client.batch_get_collection(
                names=['tv-sitcoms'])
        print('\nCollection successfully created:')
        print(response["collectionDetails"])
        # Extract the collection endpoint from the response
        host = (response['collectionDetails'][0]['collectionEndpoint'])
        final_host = host.replace("https://", "")
        self.indexData(final_host)


    def indexData(self, host):
        """Create an index and add some sample data"""
        # Build the OpenSearch client
        client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=300
        )
        # It can take up to a minute for data access rules to be enforced
        time.sleep(45)

        # Create index
        response = client.indices.create('sitcoms-eighties')
        print('\nCreating index:')
        print(response)

        # Add a document to the index.
        response = client.index(
            index='sitcoms-eighties',
            body={
                'title': 'Seinfeld',
                'creator': 'Larry David',
                'year': 1989
            },
            id='1',
        )
        print('\nDocument added:')
        print(response)
        
