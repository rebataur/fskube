import os
from pathlib import Path
import sys
import subprocess
import model
import jwt
import logging
logging.basicConfig(level=logging.INFO)
# import time

simulation = False
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(
        os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

    # ~~~ Execute commands using suprocess run ( syncronously ) and give back the results


def user_home_path():
    home = str(Path.home())
    path = os.path.join(home, '.fskube')
    try:
        os.makedirs(path)
    except OSError as e:
        pass
    return path

def cluster_home_path(cluster_id):
    home = user_home_path()
    return os.path.join(home,str(cluster_id))

def execute_command(cmd,cluster_id=None):
 
    # Signature has expired
    logging.info('##################################################')
    logging.info('------------- Executing Command ------------------')
    logging.info(f"Command > {cmd}")
    # Works for both
    path = resource_path('binaries/cli')
    env = dict(os.environ)  # make a copy of the environment

    secrets = [{'secret_name':'AWS_DEFAULT_REGION','secret_value':'test'},
               {'secret_name':'AWS_ACCESS_KEY_ID','secret_value':'test'},
               {'secret_name':'AWS_SECRET_ACCESS_KEY','secret_value':'test'}
                
            ]
    for secret in secrets:
        secret['secret_value'] = model.get_global_config_value(secret['secret_name'])   
        env[secret['secret_name']]  =   model.get_global_config_value(secret['secret_name'])      
    if cluster_id is not None:
        home_path = cluster_home_path(cluster_id)
        logging.info(os.path.join(home_path, 'kubeconfig.yaml'))
        env['KUBECONFIG'] = os.path.join(home_path, 'kubeconfig.yaml')
    env["PATH"] += os.pathsep + path  # restore the original, unmodified value
    logging.info("Running the command")
    if simulation == True:
        logging.info(cmd)
        return {'out':'', 'err': '', 'rc': 0,'success':'success'} 
    cp = subprocess.run(cmd, env=env, shell=True, universal_newlines=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logging.info("Command completed")
    logging.info('----------------- RC ----------------')
    logging.info(f'Return Code >  {cp.returncode}')
    logging.info('----------------- ERR ----------------')
    logging.info(f'Error > {cp.stderr}' ) 
    logging.info('----------------- OUT ----------------')
    success = True if cp.returncode == 0 and cp.stderr == '' else False
    return {'out': cp.stdout.replace('\n',''), 'err': cp.stderr, 'rc': cp.returncode,'success':success}


import json
if __name__ == "__main__":
    cmd = 'aws iam create-user --user-name velero1'
    output = execute_command(cmd)
    logging.info(json.loads(output['out']))