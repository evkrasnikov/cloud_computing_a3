import json
import boto3

def lambda_handler(event, context):
    # extract bucket name and key
    s3_obj = event['Records'][0]['s3']
    bucket_name = s3_obj['bucket']['name']
    object_name = s3_obj['object']['key']
    file_uri = 's3://{}/{}'.format(bucket_name, object_name)
    print(file_uri)
    
    client = boto3.client('transcribe')
    
    response = client.start_transcription_job(
        TranscriptionJobName='test',
        LanguageCode='en-US',
        Media={'MediaFileUri': file_uri},
        OutputBucketName='krasniko-ece1779-a3',
        #JobExecutionSettings={'DataAccessRoleArn':'arn:aws:iam::158238500440:role/s3read_transcribe'}
        )
    
    print(response)
    print(event)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Received file {}, transcribing!'.format(object_name))
    }
