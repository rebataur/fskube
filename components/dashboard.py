from djkube import commander
from djkube import model
import logging
logging.basicConfig(level=logging.INFO)
class Dashboard:
    def __init__(self, cluster_id):
        self.cluster_id = cluster_id   
        self.cluster = model.get_cluster(self.cluster_id) 
        self.kubectl_action = 'apply'

    def install(self):    
        # add helm repo
        cmd = f'kubectl {self.kubectl_action} -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.3.6/components.yaml'      
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('dashboard',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # update helm repo
        cmd = f'kubectl {self.kubectl_action} -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.0.0-beta8/aio/deploy/recommended.yaml'      
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('dashboard',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # helm install 
        cmd = f'kubectl {self.kubectl_action} -f https://gist.githubusercontent.com/rebataur/ab408b3598da99bb0c9ce3d1482239bf/raw/d58ba01d99b84cd5453d4426e28a19944672f9e2/eks-admin-service-account.yaml'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('dashboard',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        cmd = f'kubectl {self.kubectl_action} -f https://gist.githubusercontent.com/rebataur/9e80b36da78b163b9b98322a9e79677b/raw/58e30ddf7b8e1946b280f423666831ed65fa20f4/eks-admin-cluster-role-binding.yaml'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('dashboard',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        if self.kubectl_action == 'delete':
            return {'success':True, 'msg':'ELK Stack uninstalled successfully'}
        else:
            return {'success':True, 'msg':'ELK Stack installed successfully'}

    def uninstall(self):
        self.kubectl_action = 'delete'
        self.install()
        return {'success':True, 'msg':'velero Uninstalled Successfully'}
