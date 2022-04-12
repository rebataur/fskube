from fskube import commander
from fskube import model
import requests
from fskube import commander
import os
import json
import logging
logging.basicConfig(level=logging.INFO)
class Ingress:
    def __init__(self, cluster_id):
        self.cluster_id = cluster_id   
        self.cluster = model.get_cluster(self.cluster_id) 

    def install(self):
        p = commander.resource_path('binaries/cli')
        path = f'{p}/c{self.cluster_id}'
        self.path = path
        try:
            os.makedirs(path)
        except OSError as e:
            pass
        # associat oidc provider to cluster
        cmd = f'eksctl utils associate-iam-oidc-provider --cluster={self.cluster.name} --region {self.cluster.region} --approve'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('ingress',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # if output['rc'] != 0:
        #     return {'success':False, 'msg':'There was an error in ingress - prereq, associating iam oidc provider, please try again','output':output}

        # apply rbac
        cmd = f'kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/aws-alb-ingress-controller/v1.1.8/docs/examples/rbac-role.yaml'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('ingress',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # if output['rc'] != 0:
        #     return {'success':False, 'msg':'There was an error in ingress - prereq, installing rbac, please try again',output:output}
    
        policyARN = model.get_component_value('ALB',"ARN",None)
        if not policyARN:
        # create iam policy
            cmd = f'aws iam create-policy --policy-name ALBIngressControllerIAMPolicy --policy-document https://raw.githubusercontent.com/kubernetes-sigs/aws-alb-ingress-controller/v1.1.8/docs/examples/iam-policy.json'
            output = commander.execute_command(cmd,self.cluster_id)
            # log cmd outputs
            if (log_err_id := model.save_component_log('ingress',cmd,output,self.cluster_id)) > 0:
                info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
                logging.info(info)
            # if output['rc'] != 0:
            #     return {'success':False, 'msg':'There was an error in ingress - prereq, aws iam create-policy, please try again','output':output}

            # attach policy arn to cluster
            else:
                policyARN = json.loads(output['out'])['Policy']['Arn']
                # save config
                model.save_component_config('ALB','ARN', policyARN, self.cluster_id)

       
        policyARN = 'arn:aws:iam::827944513555:policy/ALBIngressControllerIAMPolicy'
        cmd = f'eksctl create iamserviceaccount --cluster={self.cluster.name}  --region {self.cluster.region} --namespace=kube-system --name=alb-ingress-controller --attach-policy-arn={policyARN} --override-existing-serviceaccounts --approve'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('ingress',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        alb_url = 'https://raw.githubusercontent.com/kubernetes-sigs/aws-alb-ingress-controller/v1.1.8/docs/examples/alb-ingress-controller.yaml'
        alb_yaml = requests.get(alb_url).text
        cluster_alb_yaml = alb_yaml.replace('# - --cluster-name=devCluster',f'- --cluster-name={self.cluster.name}').replace('# - --aws-region=us-west-1',f'- --aws-region={self.cluster.region}')

        cluster_alb_yaml_file_path = f'{path}/alb-ingress-controller.yaml'
        with open(cluster_alb_yaml_file_path,'w') as file:
            file.write(cluster_alb_yaml)
        cmd = f'kubectl apply -f {path}/alb-ingress-controller.yaml'
        cmd = cmd.replace('/','\\')
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('ingress',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        return {'success':True, 'msg':'ALB Ingress Installed Successfully'}

    def uninstall(self):
        p = commander.resource_path('binaries/cli')
        path = f'{p}/c{self.cluster_id}'
        cmd = f'kubectl delete -f https://raw.githubusercontent.com/kubernetes-sigs/aws-alb-ingress-controller/v1.1.8/docs/examples/rbac-role.yaml'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('ingress',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)

        policyARN = model.get_component_value('ALB',"ARN",self.cluster_id)
        cmd = f'aws iam delete-policy  --policy-arn {policyARN}'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('ingress',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        cmd = f'kubectl delete -f {path}/alb-ingress-controller.yaml'
        cmd = cmd.replace('/','\\')
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('ingress',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        return {'success':True, 'msg':'Ingress LinkerD installed successfully'}
    