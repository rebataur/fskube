import time
import datetime
from pony.orm import *
import pony.orm.dbproviders.sqlite
import os
import commander

user_home_path = commander.user_home_path()
db_file_path = os.path.join(user_home_path,'djkube')
db = Database()

db.bind(provider='sqlite', filename=db_file_path, create_db=True)


class Cluster(db.Entity):
    name = Required(str,unique=True)
    type = Required(str)
    region = Required(str,default='us-east-2')
    ttl = Optional(int)
    nodes_min = Optional(int)
    nodes_max = Optional(int)
    nodes = Optional(int)
    status = Required(str, default='Running')
    destroy_cluster = Optional(bool, default=False)
    destroy_in_min = Optional(int)
    created_at = Required(datetime.datetime, default=datetime.datetime.utcnow)

    # components
    enable_ingress = Optional(bool, default=False)
    enable_service_mesh = Optional(bool, default=False)
    enable_backup_recovery = Optional(bool, default=False)
    enable_monitoring_logging = Optional(bool, default=False)
    enable_dashboard = Optional(bool, default=False)

    component_logs = Set('ComponentLog')
    component_configs = Set('ComponentConfig')
    app_configs = Set('AppConfig')

    def creation_time_from_now(self):
        days_delta = (datetime.datetime.utcnow() - self.created_at).days
        seconds_delta = (datetime.datetime.utcnow() - self.created_at).seconds
        if days_delta != 0:
            return f'{days_delta} days ago'
        else:
            m, s = divmod(seconds_delta, 60)
            h, m = divmod(m, 60)
            return f'{h} hours {m} minutes'

class GlobalConfig(db.Entity):
    key = Required(str)
    value = Required(str)

class ComponentConfig(db.Entity):
    name = Required(str)
    key = Required(str)
    value = Required(str)
    cluster = Required(Cluster)
    updated_at = Required(datetime.datetime, default=datetime.datetime.utcnow)


class ComponentLog(db.Entity):
    name = Required(str)
    command = Required(str)
    out = Optional(str)
    err = Optional(str)
    rc = Required(int)
    cluster = Required(Cluster)
    status = Required(str, default='Not Enabled')
    updated_at = Required(datetime.datetime, default=datetime.datetime.utcnow)


class AppConfig(db.Entity):
    cluster = Required(Cluster)
    framework = Required(str) 
    app_name = Required(str)
    ingress_url = Required(str)
    no_of_replicas = Required(int, default=3)
    enable_features_logging = Required(bool, default=False)
    enable_features_network_monitoring = Required(bool, default=False)
    backup_schedule = Required(int, default=3)
    docker_registry_name = Required(str)
    github_api_token = Required(str)
    github_repo_name = Required(str)
    status = Required(str, default='Not Enabled')

    schedule_cicd = Optional(bool, default=False)
    schedule_cicd_interval = Optional(int, default=5)

    latest_release_tag_name = Optional(str)
    latest_release_title = Optional(str)
    latest_release_qa_status = Optional(str)
    latest_release_prd_status = Optional(str)
    
    current_release_tag_name_in_dev = Optional(str)
    current_release_tag_name_in_qa = Optional(str)
    current_release_tag_name_in_prd = Optional(str)
    previous_release_tag_name_in_prd = Optional(str)

# class ECRRegistry(db.Entity):
#     repository_name = Required(str)
#     image_tags = Required(str)
#     image_pushed_at = Required(datetime.datetime)

@db_session
def create_cluster(name, type, region,nodes_min,nodes_max,nodes):
    cluster = Cluster(name=name, type=type, region=region,nodes_min=nodes_min,nodes_max=nodes_max,nodes=nodes,status='Creating')
    print(cluster)
    return cluster


@db_session
def get_all_clusters():
    clusters = select(c for c in Cluster)[:]
    return clusters


@db_session
def get_cluster(cluster_id):
    return Cluster.get(id=cluster_id)


@db_session
def destroy_cluster(cluster_id):
    cluster = Cluster.get(id=cluster_id)
    cluster.status = 'Destroyed'
    cluster.destroy_cluster = True
    commit()


@db_session
def update_cluster_name(cluster_id, name):
    cluster = Cluster.get(id=cluster_id)
    cluster.name = name


@db_session
def update_cluster_status(cluster_id, status):
    cluster = Cluster.get(id=cluster_id)
    cluster.status = status
    if status == 'Error Deleted':
        cluster.name = status + '-' + str(cluster_id) 


@db_session
def update_cluster_config(cluster_id, enable_ingress, enable_service_mesh, enable_backup_restore, enable_monitoring_logging, enable_dashboard):
    cluster = Cluster.get(id=cluster_id)
    cluster.enable_ingress = enable_ingress
    cluster.enable_service_mesh = enable_service_mesh
    cluster.enable_backup_restore = enable_backup_restore
    cluster.enable_monitoring_logging = enable_monitoring_logging
    cluster.enable_dashboard = enable_dashboard
    commit()

@db_session
def update_cluster_node_count(cluster_id, nodes_min,nodes_max,nodes):
    cluster = Cluster.get(id=cluster_id)
    cluster.nodes_min = nodes_min
    cluster.nodes_max = nodes_max
    cluster.nodes = nodes

@db_session
def save_component_log(name, command, output, cluster_id):
    cluster = Cluster.get(id=cluster_id)
    cl = ComponentLog(name=name, command=command,
                      out=output['out'], err=output['err'], rc=output['rc'], cluster=cluster)
    commit()
    # check for errrors, if error return log id
    return 0 if output['rc'] == 0 and output['err'] == '' and 'error' not in output['out'].lower() else cl.id


@db_session
def save_component_config(name, key, value, cluster_id):
    # if key exists then update
    print(name, key, value, cluster_id)
    cluster = Cluster.get(id=cluster_id)
    cc = ComponentConfig.get(name=name, key=key, cluster=cluster)
    print(cc)
    if cc:
        cc.value = value
    else:
        ComponentConfig(name=name, key=key, value=value, cluster=cluster)
    commit()


@db_session
def get_component_value(name, key, cluster_id):
    if cluster_id:
        cluster = Cluster.get(id=cluster_id)

        c = ComponentConfig.get(name=name, key=key, cluster=cluster)
        return None if c is None else c.value
    # Otherwise it's a shared key,val, pick from any Cluster.
    else:
        c = ComponentConfig.get(name=name, key=key)
        return None if c is None else c.value


@db_session
def save_app_config(framework, cluster_id, app_name,ingress_url, no_of_replicas, enable_features_logging, enable_features_network_monitoring, backup_schedule, docker_registry_name, github_api_token, github_repo_name):
    cluster = Cluster.get(id=cluster_id)
    # if framework already inited then return
    ac = AppConfig.get(cluster=cluster, framework=framework)
    if ac:
        ac.set(cluster=cluster, 
                    framework=framework,               
                    ingress_url=ingress_url, 
                    app_name=app_name,
                    no_of_replicas=no_of_replicas, 
                    enable_features_logging=enable_features_logging,
                    enable_features_network_monitoring=enable_features_network_monitoring, 
                    backup_schedule=backup_schedule, 
                    docker_registry_name=docker_registry_name, 
                    github_api_token=github_api_token, 
                    github_repo_name=github_repo_name)
    else:               
        cl = AppConfig(cluster=cluster, 
                        framework=framework,               
                        ingress_url=ingress_url, 
                        app_name=app_name,
                        no_of_replicas=no_of_replicas, 
                        enable_features_logging=enable_features_logging,
                        enable_features_network_monitoring=enable_features_network_monitoring, 
                        backup_schedule=backup_schedule, 
                        docker_registry_name=docker_registry_name, 
                        github_api_token=github_api_token, 
                        github_repo_name=github_repo_name)


@db_session
def get_app_config(app_config_id):
    ac = AppConfig.get(id=app_config_id)
    return ac

@db_session
def already_inited(menu, submenu, cluster_id):
    cluster = Cluster.get(id=cluster_id)
    if menu == 'components' and exists(o for o in ComponentConfig if o.cluster == cluster ):
        return True
    elif menu == 'framework' and exists(o for o in AppConfig if o.cluster == cluster and o.framework == submenu ):
        return True
    return False

@db_session
def get_global_config_value(key):
    gc = GlobalConfig.get(key=key)
    if gc:
        return gc.value
    return None

@db_session
def set_global_config_value(key,value):
    gc = GlobalConfig.get(key=key)
    if gc:
        gc.value = value
    else:
        GlobalConfig(key=key,value=value)
    
@db_session
def get_app_config_for_cluster(cluster_id):
    cl = Cluster.get(id=cluster_id)
    return AppConfig.get(cluster=cl)

@db_session
def devsecops_development(cluster_id, schedule_cicd, schedule_cicd_interval):
    cl = Cluster.get(id=cluster_id)
    appconfig =  AppConfig.get(cluster=cl)
    appconfig.schedule_cicd = schedule_cicd
    appconfig.schedule_cicd_interval
    
@db_session
def set_current_development_tag_name(cluster_id,current_release_tag_name_in_dev):
    cl = Cluster.get(id=cluster_id)
    appconfig =  AppConfig.get(cluster=cl)
    appconfig.current_release_tag_name_in_dev = current_release_tag_name_in_dev

@db_session
def set_current_quality_tag_name(cluster_id,current_release_tag_name_in_qa):
    cl = Cluster.get(id=cluster_id)
    appconfig =  AppConfig.get(cluster=cl)
    appconfig.current_release_tag_name_in_qa = current_release_tag_name_in_qa

@db_session
def devsecops_quality(cluster_id, latest_release_tag_name, latest_release_title,latest_release_qa_status):
    cl = Cluster.get(id=cluster_id)
    appconfig =  AppConfig.get(cluster=cl)

    appconfig.latest_release_tag_name = latest_release_tag_name
    appconfig.latest_release_title = latest_release_title
    appconfig.latest_release_qa_status = latest_release_qa_status

@db_session
def devsecops_production(cluster_id, current_release_tag_name_in_prd,previous_release_tag_name_in_prd):
    cl = Cluster.get(id=cluster_id)
    appconfig =  AppConfig.get(cluster=cl)
    appconfig.current_release_tag_name_in_prd = current_release_tag_name_in_prd
    appconfig.previous_release_tag_name_in_prd = previous_release_tag_name_in_prd




db.generate_mapping(create_tables=True)
set_sql_debug(True)

