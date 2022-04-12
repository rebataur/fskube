from fskube import commander
from fskube import model
import logging
logging.basicConfig(level=logging.INFO)
class ServiceMesh:
    def __init__(self, cluster_id):
        self.cluster_id = cluster_id   
        self.cluster = model.get_cluster(self.cluster_id) 

    def install(self):     
        cmd = 'linkerd install | kubectl apply -f -'      
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        # model.save_component_log(name='linkerd',command=cmd,output=output,cluster=self.cluster)
        return {'success':True, 'msg':'ServiceMesh LinkerD installed successfully'}

    def uninstall(self):
        cmd = 'linkerd uninstall | kubectl delete -f -'
        output = commander.execute_command(cmd,self.cluster_id)
        # log cmd outputs
        if (log_err_id := model.save_component_log('elk',cmd,output,self.cluster_id)) > 0:
            info = {'success':False, 'msg':f'Error in executing in command >  {cmd},  Logs Available at > https://localhost:5000/logs/{log_err_id}'}
            logging.info(info)
        return {'success':True, 'msg':'ServiceMesh LinkerD uninstalled successfully'}