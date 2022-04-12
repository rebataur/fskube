from threading import Timer
import webbrowser
import subprocess
import json
import sys
import os
import time
import re
import zipfile
import requests
from pathlib import Path
from datetime import datetime, timedelta
import time
import shutil


from base64 import b64encode,b64decode

from nacl import encoding, public
import boto3
from github import Github
from apscheduler.schedulers.background import BackgroundScheduler
# import jwt
from flask import Flask, request, send_from_directory, url_for, render_template, redirect, jsonify
from pony.orm import *
import pony.orm.dbproviders.sqlite

import model
import commander
from costreport import CostExplorer

import logging
logging.basicConfig(level=logging.INFO)

sched = BackgroundScheduler(daemon=True)
sched.start()


app = Flask(__name__)

# ~~~ Helper functions

#~~~ Routes
   



@app.route('/test/<cmd>/<subcmd>')
def test(cmd, subcmd):  
  
    
    cmd = f'{cmd} {subcmd}'   
   
    return commander.execute_command(cmd)


def prereq_satisfied():
    aws_access_key_id=model.get_global_config_value('AWS_ACCESS_KEY_ID') 
    aws_secret_access_key=model.get_global_config_value('AWS_SECRET_ACCESS_KEY')   
    github_personal_token=model.get_global_config_value('GITHUB_PERSONAL_TOKEN')   
    print(aws_access_key_id , aws_secret_access_key , github_personal_token)
    if aws_access_key_id and aws_secret_access_key and github_personal_token:
        return {'out': None, 'err': None, 'rc': 0}

    ## DISABLING LICENSE KEY 
    
    # license_key=model.get_global_config_value('FS_KUBE_LICENSE_KEY')   
    # if not license_key:
    #     return {'out': None, 'err': "Please provide a valid license key from https://rebataur.com", 'rc': 1}
    # try:
    #     decoded = jwt.decode(license_key, '½Þý/^\x1e\x03\x8d\x88¯\x87<\x1b>¹¦B<¿¤\x08\x01@Q\x17¹Ç2{\r&\x80', algorithms=['HS256'])

    # except jwt.ExpiredSignatureError:
    #     logging.info("Your license has expired, please renew at https://rebataur.com")
    #     return {'out': None, 'err': "Your license has expired, please renew at https://rebataur.com", 'rc': 1}
    return {'out': None, 'err': None, 'rc': 1}

# ~~~ Index Route
@app.route('/')
def home(name=None):
    prereq = prereq_satisfied()
    print(prereq)
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))

    return render_template('index.html', context={})


    context = {}
    context['menu'] =  'home'
    context['submenu'] = 'dashboard'
    # result = subprocess.run(['eksctl', 'help'], stdout=subprocess.PIPE)
    # logging.info(result.stdout)
    costexplorer = CostExplorer(CurrentMonth=True)
    costexplorer.setStart(1)
    # Overall Billing Reports
    costexplorer.addReport(Name="Total", GroupBy=[], Style='Total', IncSupport=True)
    # GroupBy Reports
    costexplorer.addReport(Name="Services", GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}], Style='Total', IncSupport=True)
    # logging.info(costexplorer.reports)

    # logging.info(costexplorer.reports)
    # logging.info(costexplorer.reports[0]['Data'])
    # return 'done'
    context['previous_month_cost'] = round(costexplorer.reports[0]['Data'][0]['Total'])
    context['current_month_cost'] = round(costexplorer.reports[0]['Data'][1]['Total']) if len(costexplorer.reports[0]['Data']) > 1 else 'NA'
    if len(costexplorer.reports[0]['Data']) > 1:
        context['increase_in_cost'] = round((context['current_month_cost'] - context['previous_month_cost'])/context['previous_month_cost']*100)
    
        services = []
        total_costing_services = 0
        for k,v in costexplorer.reports[1]['Data'][1].items():
            if k != 'date' and v > 0:
                total_costing_services += 1
                services.append({'name':k,'cost':v,'percentage_cost':round(v/context['current_month_cost']*100)})

        context['services'] = services

        context['total_costing_services'] = total_costing_services
    # logging.info(context)
    return render_template('index.html', context=context)

@app.route('/configure',methods=['GET','POST'])
def configure():
    keys = ['AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_DEFAULT_REGION','AWS_DEFAULT_OUTPUT','GITHUB_PERSONAL_TOKEN','FS_KUBE_LICENSE_KEY']
    
    context = {}
    if request.method == 'POST':
        
        # check for license
        # license_key = request.form.get('FS_KUBE_LICENSE_KEY')
        # if not license_key:
        #     context['msg'] = "Please provide a valid license key from https://rebataur.com"
        #     return render_template('configure.html',context=context)
        # try:
        #     decoded = jwt.decode(license_key, '½Þý/^\x1e\x03\x8d\x88¯\x87<\x1b>¹¦B<¿¤\x08\x01@Q\x17¹Ç2{\r&\x80', algorithms=['HS256'])

        # except jwt.ExpiredSignatureError:
        #     context['msg'] = "Your license has expired, please renew at https://rebataur.com"
        #     return render_template('configure.html',context=context)

        # store the keys
        for key in keys:            
            val = request.form.get(key)
            model.set_global_config_value(key,val)
        
    return render_template('configure.html',context=context)

@app.route('/menu/<menu>/<submenu>')
def menu(menu=None, submenu=None):
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    context = {'menu': menu, 'submenu': submenu}
  
    context['clusters'] = model.get_all_clusters()

    eks_cluster_id = request.args.get('eks_cluster')
    # logging.info(eks_cluster_id)
    context['selected_cluster'] = None
    if eks_cluster_id:
        context['selected_cluster'] = model.get_cluster(eks_cluster_id)
    if model.already_inited(menu,submenu,eks_cluster_id):
        context['already_inited_msg'] = f'This cluster has been already been initialized with base settings for the {menu}->{submenu}, for administration, please use DevSecOps section or contact administrator'
    
    # for cluster full_create
    if menu == 'cluster' and submenu == 'full_create':
        regions = model.get_global_config_value('REGIONS')
        if not regions:
            regions = []
            regions_txt = commander.execute_command('aws ssm get-parameters-by-path  --path /aws/service/global-infrastructure/services/eks/regions --output json')
            regions_dict = json.loads(regions_txt['out'])['Parameters']
       
            for region in regions_dict:
                region_short_name = region['Value']
                region_long_name = commander.execute_command(f'aws ssm get-parameter --name /aws/service/global-infrastructure/regions/{region_short_name}/longName --query "Parameter.Value" --output text')['out']
                regions.append({'region_short_name':region_short_name,'region_long_name':region_long_name})
            model.set_global_config_value("REGIONS",json.dumps(regions))
            context['regions'] = regions
        else:
            context['regions'] = json.loads(regions)
        selected_region = request.args.get('cluster_region')
        logging.info(selected_region)
        if selected_region:
            context['selected_region'] = selected_region
            cmd = f'aws ec2 describe-reserved-instances-offerings --filters "Name=scope,Values=Availability Zone" --no-include-marketplace --instance-type m5.large --region {selected_region}'
            output = commander.execute_command(cmd)
            all_available_zones = json.loads(output['out'])["ReservedInstancesOfferings"] if output['out'] and len(output['out']) > 0 else []           
            applicable_zones = []
            for zone in all_available_zones:
                applicable_zones.append(zone["AvailabilityZone"])
            unique_available_zones = set(applicable_zones)
            # available_zones = json.loads(commander.execute_command(f'aws ec2 describe-availability-zones --region {selected_region}'))
            context['available_zones'] = unique_available_zones

    # for devsecops , monitoring 
    if menu == 'devsecops' and submenu == 'monitoring' and eks_cluster_id:
        cmd = 'kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes'
        node_metrics = commander.execute_command(cmd,eks_cluster_id)['out']

        cmd = 'kubectl get nodes -o json'
        node_info = commander.execute_command(cmd,eks_cluster_id)['out']
        node_info = json.loads(node_info)
        node_metrics = json.loads(node_metrics)
        for idx,node in enumerate(node_metrics['items']):
            cpu = int(node['usage']['cpu'][:-1])
            mem = int(node['usage']['memory'][:-2])
            node_metrics['items'][idx]['usage']['cpu'] = cpu
            node_metrics['items'][idx]['usage']['memory'] = mem
            
            for n_info in node_info['items']:
                if n_info['metadata']['name'] == node['metadata']['name']:
                    logging.info('=====================================================')
                    
                    node_metrics['items'][idx]['usage']['cpu_usage_pct'] = cpu / int(n_info['status']['allocatable']['cpu'][:-1])/1000000 * 100
                    node_metrics['items'][idx]['usage']['mem_usage_pct'] = mem / int(n_info['status']['allocatable']['memory'][:-2]) * 100

                    node_metrics['items'][idx]['usage']['allocatble_cpu'] = n_info['status']['allocatable']['cpu']
                    node_metrics['items'][idx]['usage']['allocatble_ephemeral_storage'] =  n_info['status']['allocatable']['ephemeral-storage']
                    node_metrics['items'][idx]['usage']['allocatble_hugepages'] = n_info['status']['allocatable']['hugepages-2Mi']
                    node_metrics['items'][idx]['usage']['allocatble_memory'] = n_info['status']['allocatable']['memory']
                    node_metrics['items'][idx]['usage']['allocatble_pods'] = n_info['status']['allocatable']['pods']

                    node_metrics['items'][idx]['usage']['conditions'] = n_info['status']['conditions']
     
     
        context['node_metrics'] = node_metrics

        # namespaces
        cmd = 'kubectl get ns -o json'
        namespaces = commander.execute_command(cmd,eks_cluster_id)['out']
        namespaces = json.loads(namespaces)

        context['namespaces'] = namespaces


        # if namespace selected
        selected_namespace = request.args.get('namespace')
        if selected_namespace:
            cmd = f'kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/{selected_namespace}/pods'
            pod_metrics = commander.execute_command(cmd,eks_cluster_id)['out'].replace('/n','')
            pod_metrics = json.loads(pod_metrics)

            cmd = f'kubectl get pods -n {selected_namespace} -o json'
            pod_info = commander.execute_command(cmd,eks_cluster_id)['out']
            pod_info = json.loads(pod_info)
            for idx,pod in enumerate(pod_metrics['items']):             
                for p_info in pod_info['items']:                    
                    # logging.info(p_info['metadata']['labels']['k8s-app'])
                    if  p_info['spec']['containers'][0]['name'] == pod['containers'][0]['name']:
                        pod_metrics['items'][idx]['conditions'] = p_info['status']['conditions']

            # logging.info(json.dumps(pod_metrics))
            context['pod_metrics'] = pod_metrics
    # for devsecops , release 
    if menu == 'devsecops' and submenu == 'release' and eks_cluster_id:
        context['release_title'],context['release_tag_name'] = get_latest_release(eks_cluster_id)
        ac = model.get_app_config_for_cluster(eks_cluster_id)
        if ac.latest_release_qa_status == 'approve_for_production':
            context['production_release_tag_name'] = ac.current_release_tag_name_in_qa


      # for devsecops , release 
    if menu == 'devsecops' and submenu == 'operations' and eks_cluster_id:
        cluster = model.get_cluster(eks_cluster_id)
       

        
    return render_template('{}.html'.format(submenu),context=context)

@app.route('/devsecops/<int:cluster_id>/<string:environment>', methods=['POST'])
def devsecops(cluster_id,environment):
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    action = request.form.get('action')
    # logging.info(cluster_id,environment,action,request)
    if environment.lower() == 'development' and action.lower() == 'schedule_cicd':
        schedule_cicd_interval = request.form.get('schedule_cicd_interval')        
        model.devsecops_development(cluster_id,  action, schedule_cicd_interval)
        
        jobs = sched.get_jobs()
        for job in jobs:
            if job.id == 'dev_cicd': 
                sched.remove_job('dev_cicd')
        
        # deploy_in_development(cluster_id)
        sched.add_job(deploy_in_development,'interval',{cluster_id},id='dev_cicd',minutes=int(schedule_cicd_interval))
        # sched.add_job(deploy_in_development,'interval',{cluster_id},id='dev_cicd',minutes=int(1))
        
    if environment.lower() == 'quality' and action.lower() == 'deploy_for_testing':
        release_tag = request.form.get('release_tag')
        release_tag_title = request.form.get('release_tag_title')   
        model.devsecops_quality(cluster_id, release_tag, release_tag_title,action)
        deploy_in_quality(cluster_id)

    if environment.lower() == 'quality' and action.lower() == 'approve_for_production':
        release_tag = request.form.get('release_tag')
        release_tag_title = request.form.get('release_tag_title')   
        model.devsecops_quality(cluster_id, release_tag, release_tag_title,action)

    if environment.lower() == 'production' and action.lower() == 'deploy_into_production':
        # if the latest release is approved for production then only deploy
        ac = model.get_app_config_for_cluster(cluster_id)
        if ac.latest_release_qa_status == 'approve_for_production':
            deploy_into_production(cluster_id)            
            # model.devsecops_production(cluster_id, ac.current_release_tag_name_in_qa,ac.current_release_tag_name_in_prd)
    if environment.lower() == 'production' and action.lower() == 'rollback_from_production':
        rollback_from_production(cluster_id)
        # model.devsecops_production(cluster_id, ac.previous_release_tag_name_in_prd,ac.previous_release_tag_name_in_prd)
    return redirect(f'/menu/devsecops/release?eks_cluster={cluster_id}')

@app.route('/destroy_cluster/<int:cluster_id>', methods=['POST'])
def destroy_cluster(cluster_id=None):
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    cluster = model.get_cluster(cluster_id)
    cluster_name,cluster_region = cluster.name, cluster.region
    cmd = f'eksctl delete cluster {cluster_name} --region {cluster_region} --wait'
    delete_output = commander.execute_command(cmd)
    if delete_output['rc'] != 0:
        return """<div class="alert alert-failure" role="alert">
            Cluster deletion failed for {} in {} region, cleanup of resources failed. Please try again.
          </div>""".format(cluster_name, cluster_region)
    else:
        model.destroy_cluster(cluster_id)
        return """<div class="alert alert-success" role="alert">
            Cluster deletion successful for {} in {} region, cleanup of resources failed. Please try again.
          </div>""".format(cluster_name, cluster_region)

@app.route('/refresh_config/<int:cluster_id>', methods=['POST'])
def refresh_config(cluster_id=None):
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    cluster = model.get_cluster(cluster_id)
    cluster_name,cluster_region = cluster.name, cluster.region
    # eksctl utils write-kubeconfig --cluster=cluster_name --region=cluster_region [--kubeconfig=<path>][--set-kubeconfig-context=<bool>]
    path = commander.cluster_home_path(cluster.id)
    full_path = os.path.join(path,'kubeconfig.yaml')
    # cmd = f'eksctl utils write-kubeconfig --cluster={cluster_name} --region={cluster_region} --kubeconfig={full_path}'
    cmd = f'aws eks --region {cluster_region} update-kubeconfig --name {cluster_name}'
    config_output = commander.execute_command(cmd,cluster.id)
    if config_output['rc'] != 0:
        return """<div class="alert alert-failure" role="alert">
            Cluster config refresh failed for {} in {} region. Please try again.
          </div>""".format(cluster_name, cluster_region)
    else:
       
        return """<div class="alert alert-success" role="alert">
            Cluster config refresh succeeded for {} in {} region. 
          </div>""".format(cluster_name, cluster_region)



@app.route('/uninstall/<int:cluster_id>', methods=['GET'])
def uninstall_components(cluster_id=None):

    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    cluster = model.get_cluster(cluster_id)
    enable_ingress,enable_service_mesh,enable_backup_restore,enable_monitoring_logging,enable_dashboard = False,False,False,False,False
    
    from components import metricserver
    ms = metricserver.MetricServer(cluster_id)
    ms.uninstall()

    from components import servicemesh
    sv = servicemesh.ServiceMesh(cluster_id)
    sv.uninstall()

    from components import backuprestore
    br = backuprestore.BackupRestore(cluster_id)
    br.uninstall()

    from components import dashboard
    db = dashboard.Dashboard(cluster_id)
    db.uninstall()

    from components import ingress
    ing = ingress.Ingress(cluster_id)
    ing.uninstall()
  
    from components import monitoringlogging
    ml = monitoringlogging.MonitoringLogging(cluster_id)
    ml.uninstall()

    return 'DONE'

@app.route('/configure_cluster/<int:cluster_id>', methods=['POST'])
def configure_cluster(cluster_id=None):
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    cluster = model.get_cluster(cluster_id)
    enable_ingress,enable_service_mesh,enable_backup_restore,enable_monitoring_logging,enable_dashboard = False,False,False,False,False
    
    # from components import metricserver
    # ms = metricserver.MetricServer(cluster_id)
    # ms.install()

    from components import servicemesh
    sv = servicemesh.ServiceMesh(cluster_id)
    sv.install()
    
    # from components import backuprestore
    # br = backuprestore.BackupRestore(cluster_id)
    # br.install()
  
    # from components import dashboard
    # db = dashboard.Dashboard(cluster_id)
    # db.install()

    # from components import ingress
    # ing = ingress.Ingress(cluster_id)
    # logging.info(ing.install())
  

    from components import monitoringlogging
    ml = monitoringlogging.MonitoringLogging(cluster_id)
    ml.install()

    # return 'DONE'
    # if request.form.get('enable_ingress'):
    #     enable_ingress = True
        
    # if request.form.get('enable_service_mesh'):
    #     enable_service_mesh = True
    #     output = commander.execute_command(cmd)
    #     logging.info(output)
    # if request.form.get('enable_backup_restore'):
    #     enable_backup_restore = True
    # if request.form.get('enable_monitoring_logging'):
    #     enable_monitoring_logging = True
    # if request.form.get('enable_dashboard'):
    #     enable_dashboard = True

    model.update_cluster_config(cluster.id,enable_ingress,enable_service_mesh,enable_backup_restore,enable_monitoring_logging,enable_dashboard)

@app.route('/cluster_operation/<int:cluster_id>', methods=['POST'])
def cluster_operation(cluster_id=None):
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    nodes_min =request.form['nodes_min']
    nodes_max =request.form['nodes_max']
    nodes =request.form['nodes']

    cluster = model.get_cluster(cluster_id)
    cmd = f'eksctl scale nodegroup --name={cluster.name}-NODEGROUP --cluster={cluster.name} --nodes={nodes} --nodes-min={nodes_min} --nodes-max={nodes_max}'
    output = commander.execute_command(cmd,cluster_id)
    if output['rc'] == 0:
        model.update_cluster_node_count(cluster_id, nodes_min,nodes_max,nodes)
    return redirect(f'/menu/devsecops/operations?eks_cluster={cluster_id}')
    
@app.route('/get_cluster', methods=['GET'])
def get_cluser():
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    cluster_id = request.args.get('eks_cluster')
    return "cluster" + cluster_id

@app.route('/quick_create', methods=['POST'])
def quick_create():
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    cluster = model.create_cluster(name='Creating',type='quick_create', region='us-east-2',nodes_min=1,nodes_max=3,nodes=2)
    # p = commander.resource_path('binaries/cli')
    # path = f'{p}\\k{cluster.id}'.replace('/','\\')
    logging.info(cluster)
    cluster_name = f'k{cluster.id}'
    path = commander.cluster_home_path(cluster.id)

    cluster_region = 'us-east-2'
    model.update_cluster_name(cluster.id,cluster_name)
    try:
        os.makedirs(path)
    except OSError as e:
        pass
    cmd = f'eksctl create cluster --name {cluster_name} --region {cluster_region} --kubeconfig={path}\\kubeconfig.yaml'

    output = commander.execute_command(cmd)
   
    logging.info(output)
    # Get cluster name if present
    # output = {
    #     'out': 'eksctl version 0.25.0\nusing region us-east-2\nsetting availability zones to [us-east-2b us-east-2a us-east-2c]\nsubnets for us-east-2b - public:192.168.0.0/19 private:192.168.96.0/19\nsubnets for us-east-2a - public:192.168.32.0/19 private:192.168.128.0/19\nsubnets for us-east-2c - public:192.168.64.0/19 private:192.168.160.0/19\nnodegroup "ng-f2fb5342" will use "ami-0277c4a966059813b" [AmazonLinux2/1.17]\nusing Kubernetes version 1.17\ncreating EKS cluster "adorable-unicorn-1598314622" in "us-east-2" region with un-managed nodes\nwill create 2 separate CloudFormation stacks for cluster itself and the initial nodegroup\nif you encounter any issues, check CloudFormation console or try \'eksctl utils describe-stacks --region=us-east-2 --cluster=adorable-unicorn-1598314622\'\nCloudWatch logging will not be enabled for cluster "adorable-unicorn-1598314622" in "us-east-2"\nyou can enable it with \'eksctl utils update-cluster-logging --region=us-east-2 --cluster=adorable-unicorn-1598314622\'\nKubernetes API endpoint access will use default of {publicAccess=true, privateAccess=false} for cluster "adorable-unicorn-1598314622" in "us-east-2"\n2 sequential tasks: { create cluster control plane "adorable-unicorn-1598314622", 2 sequential sub-tasks: { no tasks, create nodegroup "ng-f2fb5342" } }\nbuilding cluster stack "eksctl-adorable-unicorn-1598314622-cluster"\ndeploying stack "eksctl-adorable-unicorn-1598314622-cluster"\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp 52.95.18.70:443: connectex: A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to respond.) from cloudformation/DescribeStacks - will retry after delay of 46.57551ms\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp 52.95.18.70:443: connectex: A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to respond.) from cloudformation/DescribeStacks - will retry after delay of 103.73358ms\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp: lookup cloudformation.us-east-2.amazonaws.com: no such host) from cloudformation/DescribeStacks - will retry after delay of 138.230832ms\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp: lookup cloudformation.us-east-2.amazonaws.com: no such host) from cloudformation/DescribeStacks - will retry after delay of 305.612992ms\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp: lookup cloudformation.us-east-2.amazonaws.com: no such host) from cloudformation/DescribeStacks - will retry after delay of 839.40448ms\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp: lookup cloudformation.us-east-2.amazonaws.com: no such host) from cloudformation/DescribeStacks - will retry after delay of 1.104455008s\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp: lookup cloudformation.us-east-2.amazonaws.com: no such host) from cloudformation/DescribeStacks - will retry after delay of 2.657902016s\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp: lookup cloudformation.us-east-2.amazonaws.com: no such host) from cloudformation/DescribeStacks - will retry after delay of 6.232825472s\n[!]  retryable error (RequestError: send request failed\ncaused by: Post "https://cloudformation.us-east-2.amazonaws.com/": dial tcp: lookup cloudformation.us-east-2.amazonaws.com: no such host) from cloudformation/DescribeStacks - will retry after delay of 9.052512s\nbuilding nodegroup stack "eksctl-adorable-unicorn-1598314622-nodegroup-ng-f2fb5342"\n--nodes-min=2 was set automatically for nodegroup ng-f2fb5342\n--nodes-max=2 was set automatically for nodegroup ng-f2fb5342\ndeploying stack "eksctl-adorable-unicorn-1598314622-nodegroup-ng-f2fb5342"\nwaiting for the control plane availability...\nsaved kubeconfig as "C:\\\\Users\\\\pranjan24/.kube/config"\nno tasks\nall EKS cluster resources for "adorable-unicorn-1598314622" have been created\nadding identity "arn:aws:iam::827944513555:role/eksctl-adorable-unicorn-159831462-NodeInstanceRole-PPMJ6NVW77OR" to auth ConfigMap\nnodegroup "ng-f2fb5342" has 0 node(s)\nwaiting for at least 2 node(s) to become ready in "ng-f2fb5342"\nnodegroup "ng-f2fb5342" has 2 node(s)\nnode "ip-192-168-55-68.us-east-2.compute.internal" is ready\nnode "ip-192-168-94-103.us-east-2.compute.internal" is ready\nkubectl command should work with "C:\\\\Users\\\\pranjan24/.kube/config", try \'kubectl get nodes\'\nEKS cluster "adorable-unicorn-1598314622" in "us-east-2" region is ready\n', 'err': '', 'rc': 0}

    # cluster = []

    # for line in output['out'].splitlines():
    #     logging.info(line)
    #     if 'creating EKS cluster' in line:
    #         cluster = re.findall(r'"([^"]*)"', line)
    # logging.info(cluster)
    # cluster_name = cluster[0]
    # cluster_region = cluster[1]
    # # if there was an error, then do a rollback
    # logging.info(cluster_name, cluster_region)
    if output['rc'] != 0:
        cmd = f'eksctl delete cluster {cluster_name} --region {cluster_region} --wait'
        delete_output = commander.execute_command(cmd)
        model.update_cluster_status(cluster.id,status='Error Deleted')
        if delete_output['rc'] != 0:
            """<div class="alert alert-failure" role="alert">
                Cluster Creation failed for {} in {} region, cleanup of resources failed
              </div>""".format(cluster_name, cluster_region)
    else:
        model.update_cluster_status(cluster.id,status='Running')
        return """<div class="alert alert-success" role="alert">
                        Cluster Creation successful for {} in {} region
                  </div>""".format(cluster_name, cluster_region)
    return """<div class="alert alert-failure" role="alert">
                Creation of Kubernetes Cluster failed, please try again
              </div>"""





@app.route('/full_create', methods=['POST'])
def full_create():
    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))



    cluster_name = request.form['cluster_name']
    cluster_region = request.form['cluster_region']

    # p = commander.resource_path('binaries/cli')
    # path = f'{p}\\{cluster_name}'.replace('/','\\')
    cluster = model.create_cluster(name=cluster_name, type='full_create', region=cluster_region,nodes_min=3,nodes_max=6,nodes=3)

    path = commander.cluster_home_path(cluster.id)
    try:
        os.makedirs(path)
    except OSError as e:
        pass

    cluster_availability_zones = request.form.getlist(
        'cluster_availability_zones')
    cluster_managed_nodegroup = request.form['cluster_managed_nodegroup']
    # cluster_node_group_name = request.form['cluster_node_group_name']
    logging.info("~~~ Got following arguments for cluster creation")
    logging.info(cluster_name, cluster_region,
          cluster_availability_zones, cluster_managed_nodegroup)
    availability_zones = ','.join(cluster_availability_zones)
    cmd = ''
    if cluster_managed_nodegroup:
        cmd = f'eksctl create cluster --name {cluster_name} --region {cluster_region} --zones {availability_zones} --managed --nodegroup-name {cluster_name}-NODEGROUP --nodes 3 --nodes-min 3 --nodes-max 6 --kubeconfig={path}\\kubeconfig.yaml'
    else:
        cmd = f'eksctl create cluster --name {cluster_name} --region {cluster_region} --zones {availability_zones}  --nodes 3 --nodes-min 3 --nodes-max 6 --kubeconfig={path}\\kubeconfig.yaml'
    logging.info(cmd)
    output = commander.execute_command(cmd)
   
    logging.info(output)
    if output['rc'] != 0:
        cmd = f'eksctl delete cluster {cluster_name} --region {cluster_region} --wait'
        delete_output = commander.execute_command(cmd)
        model.update_cluster_status(cluster.id,status='Error Deleted')
        if delete_output['rc'] != 0:
            """<div class="alert alert-failure" role="alert">
                Cluster Creation failed for {} in {} region, cleanup of resources failed
              </div>""".format(cluster_name, cluster_region)
    else:
        model.update_cluster_status(cluster.id,status='Running')
        return """<div class="alert alert-success" role="alert">
                        Cluster Creation successful for {} in {} region
                  </div>""".format(cluster_name, cluster_region)
    return """<div class="alert alert-failure" role="alert">
                Creation of Kubernetes Cluster failed, please try again
              </div>"""


@app.route('/manage_cluster')
def manage_cluster():

    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))


    out = commander.execute_command('python -m http.server')
    logging.info(out)
    return render_template('manage_cluster.html')

# @app.route('/framework/<framework>')
# def framework(framework):
#     context = {}
    
#     context['clusters'] = model.get_all_clusters()
#     context['framework'] = framework
#     eks_cluster_id = request.args.get('eks_cluster')
#     logging.info(eks_cluster_id)
#     context['selected_cluster'] = None
#     if eks_cluster_id:
#         logging.info(model.get_cluster(eks_cluster_id))
#         context['selected_cluster'] = model.get_cluster(eks_cluster_id)


#     if framework == 'flask':
#         return render_template('framework_flask.html',context=context)


@app.route('/deploy_framework/<framework>/<cluster_id>',methods=['POST'])
def deploy_framework(framework,cluster_id):

    prereq = prereq_satisfied()
    if prereq['rc'] != 0:
        return redirect(url_for('configure'))



    logging.info(framework,cluster_id)
    logging.info(request.form)
    app_name = request.form.get('app_name')
    ingress_url = request.form.get('ingress_url')
    no_of_replicas = request.form.get('no_of_replicas')
    enable_features_logging = request.form.get('enable_features_logging')
    enable_features_network_monitoring = request.form.get('enable_features_network_monitoring')
    backup_schedule = request.form.get('backup_schedule')
    docker_registry_name = request.form.get('docker_registry_name')
    github_api_token  = github_token = model.get_global_config_value('GITHUB_PERSONAL_TOKEN')
    # request.form.get('github_api_token')
    github_repo_name = request.form.get('github_repo_name')
    model.save_app_config(framework,cluster_id,app_name,ingress_url,no_of_replicas,enable_features_logging,enable_features_network_monitoring,backup_schedule,docker_registry_name,github_api_token,github_repo_name)

    clear_download_path()
    download_link,download_file_name = get_framework_download_link(framework,github_api_token)
    logging.info(download_link)
    download_framework(download_link,download_file_name)
    download_and_unzip(download_file_name)
  
    aws_region = model.get_cluster(cluster_id).region

    # create ECR repo  
    cmd = f'aws ecr create-repository --repository-name {docker_registry_name} --region {aws_region}'   
    commander.execute_command(cmd)

    # init git repo
    init_git_repo(github_api_token, github_repo_name, download_file_name,aws_region,docker_registry_name )

    # return redirect(f'/menu/framework/django?eks_cluster={cluster_id}')
    return  """<div class="alert alert-success" role="alert">
                A repo with framework template has been created in your Github Repository
              </div>"""


def clear_download_path():
    # init the project
    download_path = os.path.join(commander.resource_path(''), "downloads")
    extracted_path = os.path.join(download_path, "extracted")    
    try:
        shutil.rmtree(download_path)
    except Exception:
        pass

    Path(extracted_path).mkdir(parents=True, exist_ok=True)

   
def get_framework_download_link(framework,github_api_token):
    g = Github(github_api_token)
    user = g.get_user()
   
    if framework.lower() == 'django':
        project_path = 'djangoproject'
        repo = g.get_repo("ranjanprj/djangoproject")
        release = repo.get_releases()[0]
        link = f'https://github.com/{repo.full_name}/archive/{release.tag_name}.zip'
        return link,f'djangoproject-{release.tag_name}.zip'.replace('-v','-')
   
    
def download_framework(download_url,download_file_name):
    download_path = os.path.join(commander.resource_path(''), "downloads")
    extracted_path = os.path.join(download_path, "extracted")    
    download_file_path = os.path.join(download_path,download_file_name)
    
    if not os.path.exists(download_file_path):
        file_to_save = open(download_file_path, "wb")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36'}
  
            with requests.get(download_url, headers=headers, timeout=5, verify=False, stream=True) as response:
                for chunk in response.iter_content(chunk_size=1024):
                    file_to_save.write(chunk)

            # remove the tag history

        except Exception as e:
            logging.info(e)
        logging.info("Completed downloading file")
    else:
        logging.info("We already have this file cached locally")


def download_and_unzip(download_file_name):
    download_path = os.path.join(commander.resource_path(''), "downloads")
    full_file_path = os.path.join(download_path,download_file_name)
    extracted_path = os.path.join(download_path, "extracted")    
    try:
        with zipfile.ZipFile(full_file_path, "r") as compressed_file:
            # logging.info(csv_path)
            compressed_file.extractall(Path(extracted_path))
    except Exception as e:
            logging.info(e)
    # logging.info("Completed un-compressing")

def init_git_repo(github_api_token, github_repo_name, download_file_name,aws_region,docker_registry_name):
    # Get the full path to the extracted project
    download_path = os.path.join(commander.resource_path(''), "downloads")    
    extracted_path = os.path.join(download_path, "extracted")   
    full_project_path = os.path.join(extracted_path,download_file_name).replace('.zip','')

    g = Github(github_api_token)
    user = g.get_user()
    repo = user.create_repo(github_repo_name)
    # repo = g.get_repo(f'ranjanprj/{github_repo_name}')
    
    for currentpath, folders, files in os.walk(full_project_path):
        logging.info('-----------')
        for file in files:
            rel_dir = os.path.relpath(currentpath, full_project_path)
            rel_file = os.path.join(rel_dir, file)
            logging.info(rel_file)
            with open(os.path.join(currentpath, file),'rb') as f:
                repo.create_file(rel_file.replace('.\\','').replace('\\','/'), "Initial Commit", f.read(), branch="master")
        # create dev and tst branches.
    repo.create_git_ref('refs/heads/feature', repo.get_commits()[0].sha)

    # dev_branch = repo.get_branch("master")
    contents = repo.get_contents(".github/workflows/master_build", ref="master")
    decoded_content = b64decode(contents.content)
    # modified_content = decoded_content.replace(b'- branch_name',b'- master').replace(b'action_name',b'release')    
    repo.delete_file(contents.path, "remove old file", contents.sha, branch="master")
    repo.create_file(f'{contents.path}.yml', "enable workflow file", decoded_content, branch="master")
    # repo.update_file(contents.path,  "change name of target branch", modified_content,contents.sha, branch="master")

    contents = repo.get_contents(".github/workflows/feature_build", ref="master")
    decoded_content = b64decode(contents.content)
    # modified_content = decoded_content.replace(b'- branch_name',b'- feature')
    repo.delete_file(contents.path, "remove old file", contents.sha, branch="master")
    repo.create_file(f'{contents.path}.yml', "enable workflow file", decoded_content, branch="feature")
    # repo.update_file(contents.path,  "change name of target branch", modified_content,contents.sha, branch="master")

    # delete files from feature as well 
    contents = repo.get_contents(".github/workflows/master_build", ref="feature")
    repo.delete_file(contents.path, "remove old file", contents.sha, branch="feature")

    contents = repo.get_contents(".github/workflows/feature_build", ref="feature")
    repo.delete_file(contents.path, "remove old file", contents.sha, branch="feature")


    #create secrets
    secrets = [{'secret_name':'AWS_ACCESS_KEY_ID','secret_value':'test'},
               {'secret_name':'AWS_SECRET_ACCESS_KEY','secret_value':'test'},
    
            ]
    for secret in secrets:
        secret['secret_value'] = model.get_global_config_value(secret['secret_name'])        
        create_github_secrets(secret['secret_name'],secret['secret_value'],repo.owner.login,github_repo_name,github_api_token)
    # Create secret for region
    create_github_secrets('AWS_REGION',aws_region,repo.owner.login,github_repo_name,github_api_token)
    create_github_secrets('ECR_REPOSITORY',docker_registry_name,repo.owner.login,github_repo_name,github_api_token)
    
def create_github_secrets(secret_name,secret_value,owner,github_repo_name,github_api_token):   
    g = Github(github_api_token)
    user = g.get_user() 
    headers = {'Authorization': 'token ' + github_api_token}
    logging.info(f'https://api.github.com/repos/{owner}/{github_repo_name}/actions/secrets/public-key')
    res = requests.get(f'https://api.github.com/repos/{owner}/{github_repo_name}/actions/secrets/public-key', headers=headers)
    key_id = res.json()['key_id']
    key_value = res.json()['key']
    encrypted_value = encrypt(key_value,secret_value)
    payload = {'key_id':key_id,'encrypted_value':encrypted_value}
    res = requests.put(f'https://api.github.com/repos/{owner}/{github_repo_name}/actions/secrets/{secret_name}', headers=headers, data=json.dumps(payload))
    logging.info(res.text)
def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    logging.info(public_key,secret_value)
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")

def get_latest_release(cluster_id):
    try:
        github_token = model.get_global_config_value('GITHUB_PERSONAL_TOKEN')
        g = Github(github_token)
        user = g.get_user()
        app_cnf = model.get_app_config_for_cluster(cluster_id)
        logging.info(f'{user.login}/{app_cnf.github_repo_name}')
        repo = g.get_repo(f'{user.login}/{app_cnf.github_repo_name}')
        release = repo.get_latest_release()
        return release.title,release.tag_name
    except Exception as e:
        return 'NA','NA'

def deploy_in_development(cluster_id):
    path = commander.resource_path('binaries/cli')
    cluster_manifests_path = f'{path}/c{cluster_id}/manifests/development'
    try:
        shutil.rmtree(cluster_manifests_path)
    except Exception:
        pass
    ac = model.get_app_config_for_cluster(cluster_id)
    # get the latest commit from github
    github_token = model.get_global_config_value('GITHUB_PERSONAL_TOKEN')
    g = Github(github_token)
    user = g.get_user()
    app_cnf = model.get_app_config_for_cluster(cluster_id)
    logging.info(f'{user.login}/{app_cnf.github_repo_name}')
    repo = g.get_repo(f'{user.login}/{app_cnf.github_repo_name}').get_branch("feature")

    latest_commit_sha = repo.commit.sha
    logging.info('-----------------')
    logging.info(latest_commit_sha,ac.current_release_tag_name_in_dev)

    # if this already deployed don't bother
    if latest_commit_sha == ac.current_release_tag_name_in_dev:
        return None,None
    # check the container tag exists in ECR
    output = commander.execute_command(f'aws ecr list-images --repository-name {app_cnf.docker_registry_name}')
    image_list = json.loads(output['out'])

    image_exists = False
    for image in image_list["imageIds"]:
        logging.info(image)
        if 'imageTag' in image and latest_commit_sha == image["imageTag"]:
            logging.info(latest_commit_sha , image["imageTag"])
            image_exists = True    
    
    if not image_exists:
        return None,None
    # change the manifest file to reflect latest container locally
    # Get ECR URI
    output = commander.execute_command(f'aws ecr describe-repositories --repository-name {app_cnf.docker_registry_name}')
    ecr_repo_uri = json.loads(output['out'])["repositories"][0]["repositoryUri"]
    try:
        os.makedirs(cluster_manifests_path)
    except Exception as e: # Python >2.5
        logging.info(e)
    # full_manifests_path = f'{cluster_manifests_path}/manifests.yml'
    repo = g.get_repo(f'{user.login}/{app_cnf.github_repo_name}')
    contents = repo.get_contents("manifests", ref="feature")
    while contents:
        file_content = contents.pop(0)
        if file_content.type == "dir":
            contents. extend(repo.get_contents(file_content.path))
        else:
            logging.info(file_content)
            decoded_content = b64decode(file_content.content).decode('utf8')
            logging.info(decoded_content)
            with open(f'{cluster_manifests_path}/{file_content.name}','w+') as f:
                
                if file_content.name == 'app.yaml':
                    full_uri = f'{ecr_repo_uri}:{latest_commit_sha}'
                    decoded_content = decoded_content.format(app_image=full_uri,app_name=ac.app_name.lower(),replicas=1,environment='development')
                else:
                    decoded_content = decoded_content.format(environment='development')
                f.write(decoded_content) 
    output = commander.execute_command(f'kubectl apply -f {cluster_manifests_path}\\namespace.yml',cluster_id)
    output = commander.execute_command(f'kubectl apply -f {cluster_manifests_path}\\.',cluster_id)  

    if output and output['rc'] == 0:
            model.set_current_development_tag_name(cluster_id,latest_commit_sha)
  

def deploy_in_quality(cluster_id):
    path = commander.resource_path('binaries/cli')
    cluster_manifests_path = f'{path}/c{cluster_id}/manifests/quality'
    ac = model.get_app_config_for_cluster(cluster_id)
    # get the latest release from github
    github_token = model.get_global_config_value('GITHUB_PERSONAL_TOKEN')
    g = Github(github_token)
    user = g.get_user()
    app_cnf = model.get_app_config_for_cluster(cluster_id)
    logging.info(f'{user.login}/{app_cnf.github_repo_name}')
    repo = g.get_repo(f'{user.login}/{app_cnf.github_repo_name}')
    latest_release = repo.get_latest_release()
    latest_release_tag_name = latest_release.tag_name
     # if this already deployed don't bother
    if latest_release_tag_name == ac.current_release_tag_name_in_qa:
        return None,None
    # check the container tag exists in ECR
    output = commander.execute_command(f'aws ecr list-images --repository-name {app_cnf.docker_registry_name}')
    image_list = json.loads(output['out'])
    image_exists = False
    for image in image_list["imageIds"]:
        if 'imageTag' in image and latest_release_tag_name == image["imageTag"]:
            image_exists = True    
    
    if not image_exists:
        return
    # change the manifest file to reflect latest container locally
    # Get ECR URI
    output = commander.execute_command(f'aws ecr describe-repositories --repository-name {app_cnf.docker_registry_name}')
    ecr_repo_uri = json.loads(output['out'])["repositories"][0]["repositoryUri"]
    try:
        os.makedirs(cluster_manifests_path)
    except Exception as exc: # Python >2.5
        logging.info(exc)
    # full_manifests_path = f'{cluster_manifests_path}/manifests.yml'
    contents = repo.get_contents("manifests", ref="master")
    while contents:
        file_content = contents.pop(0)
        if file_content.type == "dir":
            contents. extend(repo.get_contents(file_content.path))
        else:
            decoded_content = b64decode(file_content.content).decode('utf8')
            logging.info(decoded_content)
            with open(f'{cluster_manifests_path}/{file_content.name}','w+') as f:
                
                if file_content.name == 'app.yaml':
                    full_uri = f'{ecr_repo_uri}:{latest_release_tag_name}'
                    decoded_content = decoded_content.format(app_image=full_uri,app_name=ac.app_name.lower(),replicas=1,environment='quality')
                else:
                    decoded_content = decoded_content.format(environment='quality')
                f.write(decoded_content) 
    output = commander.execute_command(f'kubectl apply -f {cluster_manifests_path}\\namespace.yml',cluster_id)
    output = commander.execute_command(f'kubectl apply -f {cluster_manifests_path}\\.',cluster_id)  
    if output and output['rc'] == 0:
            model.set_current_quality_tag_name(cluster_id,latest_release_tag_name)


def deploy_into_production(cluster_id):
    path = commander.resource_path('binaries/cli')
    cluster_manifests_path = f'{path}/c{cluster_id}/manifests/production'
    ac = model.get_app_config_for_cluster(cluster_id)
    # get the latest release from github
    github_token = model.get_global_config_value('GITHUB_PERSONAL_TOKEN')
    g = Github(github_token)
    user = g.get_user()
    app_cnf = model.get_app_config_for_cluster(cluster_id)
    logging.info(f'{user.login}/{app_cnf.github_repo_name}')
    repo = g.get_repo(f'{user.login}/{app_cnf.github_repo_name}')
    latest_release = repo.get_latest_release()
    latest_release_tag_name = ac.current_release_tag_name_in_qa
     # if this already deployed don't bother
    if latest_release_tag_name == ac.current_release_tag_name_in_prd:
        return None,None
    # check the container tag exists in ECR
    output = commander.execute_command(f'aws ecr list-images --repository-name {app_cnf.docker_registry_name}')
    image_list = json.loads(output['out'])
    image_exists = False
    for image in image_list["imageIds"]:
        if 'imageTag' in image and latest_release_tag_name == image["imageTag"]:
            image_exists = True    
    
    if not image_exists:
        return
    # change the manifest file to reflect latest container locally
    # Get ECR URI
    output = commander.execute_command(f'aws ecr describe-repositories --repository-name {app_cnf.docker_registry_name}')
    ecr_repo_uri = json.loads(output['out'])["repositories"][0]["repositoryUri"]
    try:
        os.makedirs(cluster_manifests_path)
    except Exception as exc: # Python >2.5
        logging.info(exc)
    # full_manifests_path = f'{cluster_manifests_path}/manifests.yml'
    contents = repo.get_contents("manifests", ref="master")
    while contents:
        file_content = contents.pop(0)
        if file_content.type == "dir":
            contents. extend(repo.get_contents(file_content.path))
        else:
            decoded_content = b64decode(file_content.content).decode('utf8')
            logging.info(decoded_content)
            with open(f'{cluster_manifests_path}/{file_content.name}','w+') as f:
                
                if file_content.name == 'app.yaml':
                    full_uri = f'{ecr_repo_uri}:{latest_release_tag_name}'
                    decoded_content = decoded_content.format(app_image=full_uri,app_name=ac.app_name.lower(),replicas=1,environment='production')
                else:
                    decoded_content = decoded_content.format(environment='production')
                f.write(decoded_content) 
    output = commander.execute_command(f'kubectl apply -f {cluster_manifests_path}\\namespace.yml',cluster_id)
    output = commander.execute_command(f'kubectl apply -f {cluster_manifests_path}\\.',cluster_id)  
    if output and output['rc'] == 0:
            model.devsecops_production(cluster_id,latest_release_tag_name,ac.current_release_tag_name_in_prd )   
    output = commander.execute_command('kubectl get -n production deploy -o yaml | linkerd inject - | kubectl apply -f -',cluster_id) 
def rollback_from_production(cluster_id):
    # rollback
    # kubectl rollout undo deployment 
    app_cnf = model.get_app_config_for_cluster(cluster_id)
    output = commander.execute_command(f'kubectl rollout undo deployment.v1.apps/{app_cnf.app_name} -n production',cluster_id)
    if output and output['rc'] == 0:
        model.devsecops_production(cluster_id, app_cnf.previous_release_tag_name_in_prd,app_cnf.previous_release_tag_name_in_prd)


    # Run kubectl and deploy the project 
# ~~~~ Invoke the webbrowser
def open_browser():
    webbrowser.open_new('http://localhost:5000/')




# ~~~ The main function
if __name__ == "__main__":
    # Timer(10, open_browser).start()
    logging.getLogger('werkzeug').disabled = True
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'
    
    logo = '''
    -------------------------------------------------------------------------------
    |           Welcome to "fsKube" - Your Full Stack Kubernetes Enabler          |  
    |                                                                             |
    |           To access the application just head over to                       |
    |           http://localhost:5678                                             |
    |                                                                             |
    --------------------------------------------------------------------------------
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@@@@@@
    @@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@@@@
    @@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@@
    @@@@@@&%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@
    @@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%/      ,#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@
    @@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%/    *%%%%%%(.   ,#%%%%%%%%%%%%%%%%%%%%%%%%%%#@@@
    @@@%%%%%%%%%%%%%%%%%%%%%%%/    *%%%%%%%%%%%%%%%%#.   ,#%%%%%%%%%%%%%%%%%%%%%%%@@
    @&%%%%%%%%%%%%%%%%%%%/    /%%%%%%%%%%%%%%%%%%%%%%%%%%#.   .#%%%%%%%%%%%%%%%%%%%@
    @%%%%%%%%%%%%%%%%,   /%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#.   (%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%#   /%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#,  /%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%%%%%*    /%%%%%%%%%%%%%%%%%%%%%%%%%%%%#,   .#%%%%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%%#.   ,#%*    /%%%%%%%%%%%%%%%%%%#,   .#%(    *%%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%(  (%%%%%%%%%%*    /%%%%%%%%#.   .#%%%%%%%%%%, *%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%%%#,   .(%%%%%%%%%%*        .#%%%%%%%%%%*    (%%%%%%%%%%%%%%%%%%
    %%%%%%%%%%%%%%%%%%#,   .,   .(%%%%%%%%%%%%%%%%%%%%%*    ,    /%%%%%%%%%%%%%%%%%%
    @%%%%%%%%%%%%%%%(  (%%%%%%%%#,   .(%%%%%%%%%%%*    (%%%%%%%%%, *%%%%%%%%%%%%%%%&
    @&%%%%%%%%%%%%%%%#.   ,#%%%%%%%%%#,   .(#*    (%%%%%%%%%%/    /%%%%%%%%%%%%%%%%@
    @@%%%%%%%%%%%%%%%%%%%%(.   ,#%%%%%%%%%%((#%%%%%%%%%%/    *%%%%%%%%%%%%%%%%%%%%@@
    @@@%%%%%%%%%%%%%%%%%%%%%%%%(.   ,#%%%%%%%%%%%%%/    *%%%%%%%%%%%%%%%%%%%%%%%%%@@
    @@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%(.   ,#%%%/    *%%%%%%%%%%%%%%%%%%%%%%%%%%%%&@@@
    @@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%#.   /%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%&@@@@@
    @@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@
    @@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%&@@@@@@@@
    @@@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%&@@@@@@@@@@
    @@@@@@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%&@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@&%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@%%%%%%%%%%%%%%%%%%%%%%%%%%@@@@@@@@@@@@@@@@@@@@@@@@@@@
    '''

    logging.info(logo)
    app.run(debug=True, port=5678)
