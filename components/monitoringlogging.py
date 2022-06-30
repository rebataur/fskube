from djkube import commander
from djkube import model
import time
import logging
logging.basicConfig(level=logging.INFO)
class MonitoringLogging:
    def __init__(self, cluster_id):
        self.cluster_id = cluster_id   
        self.cluster = model.get_cluster(self.cluster_id) 

    def install(self):   
        # add helm repo
        cmd = 'kubectl create namespace logging'      
        output = commander.execute_command(cmd,self.cluster_id)
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)

        # add helm repo
        cmd = 'helm repo add elastic https://helm.elastic.co'      
        output = commander.execute_command(cmd,self.cluster_id)
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)

        # update helm repo
        cmd = 'helm repo update'      
        output = commander.execute_command(cmd,self.cluster_id)
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # helm install 
        cmd = 'helm install  elasticsearch elastic/elasticsearch -f https://gist.githubusercontent.com/rebataur/360812a9d482278d075d96c24b206730/raw/6c90f2343a6cae1db387cb2e3d53934cf8a2b7ff/elkvalues   --namespace logging'      
        output = commander.execute_command(cmd,self.cluster_id)
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        time.sleep(60*3)
        cmd = 'helm install  kibana elastic/kibana   --namespace logging'      
        output = commander.execute_command(cmd,self.cluster_id)
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        time.sleep(60*3)
        cmd = 'helm install filebeat elastic/filebeat   --namespace logging'      
        output = commander.execute_command(cmd,self.cluster_id)
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        time.sleep(60*3)
        cmd = 'helm install  metricbeat elastic/metricbeat   --namespace logging'      
        output = commander.execute_command(cmd,self.cluster_id)
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        return {'success':True, 'msg':'ELK Stack installed successfully'}

    def uninstall(self):
        cmd = 'helm delete elasticsearch kibana filebeat metricbeat   --namespace logging'      
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        return {'success':True, 'msg':'ELK Stack installed successfully'}
        