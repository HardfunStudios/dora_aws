import json
import os
import pprint as pp
import time
import tempfile
from utility import Utility
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

class SyncClient:
    def __init__(
        self, boto3_session, bedrock_agent_client, runtime_client, lambda_client, iam_resource, aoss_client, s3_client, postfix
    ):
        self.boto3_session = boto3_session
        self.iam_resource = iam_resource
        self.lambda_client = lambda_client
        self.bedrock_agent_runtime_client = runtime_client
        self.bedrock_agent_client = bedrock_agent_client
        self.aoss_client = aoss_client
        self.s3_client = s3_client
        self.postfix = postfix
        
        self.utility = None
        
        self.course_id = None
        self.bucket_name = None
        self.index_name = None
        self.vector_store_host = None
        self.collection = None
        self.encryption_policy = None 
        self.network_policy = None
        self.access_policy = None
        self.bedrock_kb_execution_role_arn = None
        self.kb = None
        self.ds = None
        
    def create_course_knowledge_base(self, course_id, course_content, data = None):
        self.course_id = course_id 
        self.bucket_name = f"course-bot-{self.postfix}-{self.course_id}" 
        self.suffix = f"{self.postfix}-{self.course_id}"
        self.utility = Utility(self.suffix, self.boto3_session)
        if not data:
            self._create_vector_store()
            self._create_vector_index()
            self._upload_data_to_s3(course_content)
            self._create_knowledge_base()
            self._start_ingestion_job()
        else:
            self.kb['knowledgeBaseId'] = data['knowledgeBaseId']
            self.ds['dataSourceId'] = data['dataSourceId']
            self._upload_data_to_s3(course_content)
            self._start_ingestion_job()
            
        return self.to_dict()
    
    def to_dict(self): 
        return {
            "course_id": self.course_id,
            "bucket_name": self.bucket_name,
            "vector_store_host": self.vector_store_host,
            "collection": self.collection,
            "encryption_policy": self.encryption_policy,
            "network_policy": self.network_policy,
            "access_policy": self.access_policy,
            "bedrock_kb_execution_role_arn": self.bedrock_kb_execution_role_arn,
            "kb": self.kb,
            
            "dataSourceId": self.ds['dataSourceId'],
            "knowledgeBaseId": self.kb['knowledgeBaseId'],
            "index_name": self.index_name,
            "collection_id": self.collection['createCollectionDetail']['id'],
            "access_policy": self.access_policy['accessPolicyDetail']['name'],
            "network_policy": self.network_policy['securityPolicyDetail']['name'],
            "encryption_policy": self.encryption_policy['securityPolicyDetail']['name'],  
        }
    
    def _create_vector_store(self):
        vector_store_name = f'bedrock-rag-{self.suffix}'
        self.index_name = f"bedrock-rag-index-{self.suffix}"
        bedrock_kb_execution_role = self.utility.create_bedrock_execution_role(bucket_name=self.bucket_name)
        self.bedrock_kb_execution_role_arn = bedrock_kb_execution_role['Role']['Arn']

        self.encryption_policy, self.network_policy, self.access_policy = self.utility.create_policies_in_oss(
            vector_store_name=vector_store_name,
            aoss_client=self.aoss_client,
            bedrock_kb_execution_role_arn=self.bedrock_kb_execution_role_arn
        )
        self.collection = self.aoss_client.create_collection(name=vector_store_name,type='VECTORSEARCH')

        collection_id = self.collection['createCollectionDetail']['id']
        self.vector_store_host = collection_id + '.us-east-1.aoss.amazonaws.com'
        self.utility.create_oss_policy_attach_bedrock_execution_role(collection_id=collection_id,
                                                    bedrock_kb_execution_role=bedrock_kb_execution_role)


    def _create_vector_index(self):

        credentials = self.boto3_session.get_credentials()
        awsauth = auth = AWSV4SignerAuth(credentials, 'us-east-1', 'aoss')

        self.index_name = f"bedrock-index-{self.suffix}"
        body_json = {
        "settings": {
            "index.knn": "true"
        },
        "mappings": {
            "properties": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": 1536
                },
                "text": {
                    "type": "text"
                },
                "text-metadata": {
                    "type": "text"         }
            }
        }
        }
        # Build the OpenSearch client
        self.oss_client = OpenSearch(
            hosts=[{'host': self.vector_store_host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=300
        )
        # # It can take up to a minute for data access rules to be enforced
        time.sleep(60)

        # Create index
        response = self.oss_client.indices.create(index=self.index_name, body=json.dumps(body_json))
        print('\nCreating index:')
        print(response)


    def _upload_data_to_s3(self, course_content):
        s3 = self.boto3_session.resource('s3')
        if s3.Bucket(self.bucket_name) not in s3.buckets.all():
            s3.create_bucket(Bucket=self.bucket_name)
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
            tmp.write(course_content.encode())
            tmp_file_name = tmp.name

        # Fazer upload do arquivo para o S3
        self.s3_client.upload_file(tmp_file_name, self.bucket_name, os.path.basename(tmp_file_name))

        # Remover o arquivo temporário após o upload
        os.remove(tmp_file_name)        
    
    def _create_knowledge_base(self):

        opensearchServerlessConfiguration = {
                    "collectionArn": self.collection["createCollectionDetail"]['arn'],
                    "vectorIndexName": self.index_name,
                    "fieldMapping": {
                        "vectorField": "vector",
                        "textField": "text",
                        "metadataField": "text-metadata"
                    }
                }

        chunkingStrategyConfiguration = {
            "chunkingStrategy": "FIXED_SIZE",
            "fixedSizeChunkingConfiguration": {
                "maxTokens": 512,
                "overlapPercentage": 20
            }
        }

        s3Configuration = {
            "bucketArn": f"arn:aws:s3:::{self.bucket_name}",
        }

        embeddingModelArn = f"arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1"

        name = f"bedrock-knowledge-base-{self.suffix}"
        description = "Amazon shareholder letter knowledge base."
        roleArn = self.bedrock_kb_execution_role_arn
                
        try:
            create_kb_response = self.bedrock_agent_client.create_knowledge_base(
                name = name,
                description = description,
                roleArn = roleArn,
                knowledgeBaseConfiguration = {
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": embeddingModelArn
                    }
                },
                storageConfiguration = {
                    "type": "OPENSEARCH_SERVERLESS",
                    "opensearchServerlessConfiguration":opensearchServerlessConfiguration
                }
            )
            self.kb = create_kb_response["knowledgeBase"]
        except Exception as err:
            print(f"{err=}, {type(err)=}")


        get_kb_response = self.bedrock_agent_client.get_knowledge_base(knowledgeBaseId = self.kb['knowledgeBaseId'])

        create_ds_response = self.bedrock_agent_client.create_data_source(
            name = name,
            description = description,
            knowledgeBaseId = self.kb['knowledgeBaseId'],
            dataSourceConfiguration = {
                "type": "S3",
                "s3Configuration":s3Configuration
            },
            vectorIngestionConfiguration = {
                "chunkingConfiguration": chunkingStrategyConfiguration
            }
        )
        self.ds = create_ds_response["dataSource"]



    def _start_ingestion_job(self):
        start_job_response = self.bedrock_agent_client.start_ingestion_job(knowledgeBaseId = self.kb['knowledgeBaseId'], dataSourceId = self.ds["dataSourceId"])
        job = start_job_response["ingestionJob"]
        
        
        while(job['status']!='COMPLETE' ):
            get_job_response = self.bedrock_agent_client.get_ingestion_job(
                knowledgeBaseId = self.kb['knowledgeBaseId'],
                    dataSourceId = self.ds["dataSourceId"],
                    ingestionJobId = job["ingestionJobId"]
            )
            job = get_job_response["ingestionJob"]
            pp.pprint(job)
            time.sleep(10)
            
        kb_id = self.kb["knowledgeBaseId"]
        pp.pprint(kb_id)
        
        
    def delete_course_bot(self, course_id, data):
        self.suffix = f"{self.postfix}-{course_id}"
        self.utility = Utility(self.suffix, self.boto3_session)
        
        self.bedrock_agent_client.delete_data_source(dataSourceId = data['dataSourceId'], knowledgeBaseId=data['knowledgeBaseId'])
        self.bedrock_agent_client.delete_knowledge_base(knowledgeBaseId=data['knowledgeBaseId'])
        self.oss_client.indices.delete(index=data['index_name'])
        self.aoss_client.delete_collection(id=data['collection_id'])
        self.aoss_client.delete_access_policy(type="data", name=data['access_policy'])
        self.aoss_client.delete_security_policy(type="network", name=data['network_policy'])
        self.aoss_client.delete_security_policy(type="encryption", name=data['encryption_policy'])
        self.utility.delete_iam_role_and_policies(self.suffix)



