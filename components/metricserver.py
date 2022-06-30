from djkube import commander
from djkube import model
import logging
logging.basicConfig(level=logging.INFO)
class MetricServer:
    def __init__(self, cluster_id):
        self.cluster_id = cluster_id   
        self.cluster = model.get_cluster(self.cluster_id) 
  
    def install(self):     
        cmd = 'kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.3.7/components.yaml'      
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('metricserver',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # model.save_component_log(name='linkerd',command=cmd,output=output,cluster=self.cluster)
        return {'success':True, 'msg':'Metric Server installed successfully','out':output}

    def uninstall(self):
        cmd = 'kubectl delete -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.3.7/components.yaml'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('metricserver',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        return {'success':True, 'msg':'Metric Server  uninstalled successfully'}