from fskube import commander
from fskube import model
import requests
import json
import os
import logging
logging.basicConfig(level=logging.INFO)

class BackupRestore:
    def __init__(self, cluster_id):
        self.cluster_id = cluster_id   
        self.cluster = model.get_cluster(self.cluster_id) 

    def install(self):
        p = commander.resource_path('binaries/cli')
        path = f'{p}/c{self.cluster_id}'
        try:
            os.makedirs(path)
        except OSError as e:
            pass
        # create a bucket
        bucket_name = f'c{self.cluster_id}-velero-bucket'
        cmd = f'aws s3 mb s3://{bucket_name}'
        output = commander.execute_command(cmd,self.cluster_id)

        # log cmd outputs
        if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        
        # save config
        model.save_component_config('velero','BucketName', bucket_name, self.cluster_id)

        
        # check whether user already exists
        user_name = model.get_component_value('velero','User.UserName',self.cluster_id)   
        if not user_name: 
            # Create user
            user_name = f'c{self.cluster_id}-velero-user'    
            cmd = f'aws iam create-user --user-name {user_name}'
            output = commander.execute_command(cmd,self.cluster_id)
            # log cmd outputs
            if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
                info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
                logging.info(info)
        
            # store the output in database
            
            out = json.loads(output['out'])
            model.save_component_config('velero','User.UserName',user_name,self.cluster_id)
            model.save_component_config('velero','User.UserId', out['User']['UserId'],self.cluster_id)
            model.save_component_config('velero','User.Arn', out['User']['Arn'],self.cluster_id)

            # create iam policy
            policy_json = """{
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ec2:DescribeVolumes",
                            "ec2:DescribeSnapshots",
                            "ec2:CreateTags",
                            "ec2:CreateVolume",
                            "ec2:CreateSnapshot",
                            "ec2:DeleteSnapshot"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:DeleteObject",
                            "s3:PutObject",
                            "s3:AbortMultipartUpload",
                            "s3:ListMultipartUploadParts"
                        ],
                        "Resource": [
                            "arn:aws:s3:::bucket_name/*"
                        ]
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:ListBucket"
                        ],
                        "Resource": [
                            "arn:aws:s3:::bucket_name"
                        ]
                    }
                ]
            }""".replace('bucket_name',bucket_name)

            # write the policy
            velory_policy_file = f'{path}/velero-policy.json'
            with open(velory_policy_file,'w') as file:
                file.write(policy_json)

            # apply the policy
            cmd = f'aws iam put-user-policy --user-name {user_name} --policy-name velero --policy-document file://{path}/velero-policy.json'
            output = commander.execute_command(cmd,self.cluster_id)
            # log cmd outputs
            if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:

                info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
                logging.info(info)
    
        # ACCESS KEYS
        # create access key file
        access_key_file = f'{path}/velero-access-key.json'

        # check whether key exists in database
        access_key_id = model.get_component_value('velero','User.AccessKeyId',self.cluster_id)
        # if not os.path.isfile(access_key_file):
        if not access_key_id:
            cmd = f'aws iam create-access-key --user-name  {user_name}'
            output = commander.execute_command(cmd,self.cluster_id)
            # log cmd outputs
            if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
                info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
                logging.info(info)
            access_keys = json.loads(output['out'])
            
            with open(access_key_file,'w') as file:
                file.write(output['out'])
            creds_file = f'{path}/velero-credentials.json'

            # store the output in database
            out = json.loads(output['out'])
            model.save_component_config('velero','User.AccessKeyId',out['AccessKey']['AccessKeyId'],self.cluster_id)
            model.save_component_config('velero','User.SecretAccessKey',out['AccessKey']['SecretAccessKey'],self.cluster_id)
        
        # In any case generate the credentials file
        access_key_id = model.get_component_value('velero','User.AccessKeyId',self.cluster_id)
        secret_access_key = model.get_component_value('velero','User.SecretAccessKey',self.cluster_id)
        creds_file = f'{path}/velero-credentials.json'
        with open(creds_file,'w') as file:
            str = """[default]\naws_access_key_id={}\naws_secret_access_key={}""".format(access_key_id, secret_access_key)
            file.write(str)


        cmd = f'velero install --provider aws --plugins velero/velero-plugin-for-aws:v1.1.0 --bucket {bucket_name} --backup-location-config region={self.cluster.region} --snapshot-location-config region={self.cluster.region} --secret-file {path}/velero-credentials.json'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        return {'success':True, 'msg':'velero Installed Successfully'}

    def uninstall(self):
        p = commander.resource_path('binaries/cli')
        path = f'{p}/c{self.cluster_id}'
        # delete the bucket
        cmd = f'kubectl  delete namespace/velero clusterrolebinding/velero'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        cmd = 'kubectl delete crds -l component=velero'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # delete the bucket
        bucket_name = model.get_component_value('velero','BucketName',self.cluster_id)
        cmd = f'aws s3 rb --force s3://{bucket_name}'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # delete policy
        username = model.get_component_value('velero','User.UserName',self.cluster_id)
        cmd = f'aws iam delete-user-policy --user-name {username} --policy-name velero'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)

        # delete access key
        access_key = model.get_component_value('velero','User.AccessKeyId',self.cluster_id)
        cmd = f'aws iam delete-access-key --access-key-id {access_key} --user-name {username}'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # delete the user
        username = model.get_component_value('velero','User.UserName',self.cluster_id)
        cmd = f'aws iam delete-user --user-name {username}'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('velero',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        return {'success':True, 'msg':'velero Uninstalled Successfully'}
