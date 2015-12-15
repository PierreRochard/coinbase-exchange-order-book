from pprint import pformat
import os

from fabric.decorators import parallel
from fabric.api import cd, env, get
from fabric.operations import run
from boto3.session import Session
from botocore.exceptions import ClientError

from aws_config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, REGION, KEY_PAIR_NAME

session = Session(aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                  region_name=REGION)

client = session.client('ec2')
ec2 = session.resource('ec2')

private_key_file = os.path.abspath('../keys/{0}.pem'.format(KEY_PAIR_NAME))
if not os.path.isfile(private_key_file):
    print('Creating new keys')
    key = client.create_key_pair(KeyName=KEY_PAIR_NAME)
    with open(private_key_file, 'w') as f:
        f.write(key['KeyMaterial'])

instances = ec2.instances.all()
subnets = client.describe_subnets()['Subnets']
availability_zones = {subnet['SubnetId']: subnet['AvailabilityZone'] for subnet in subnets}

instance_availability_zones = {instance.public_dns_name: availability_zones[instance.subnet_id] for instance in instances
      if instance.state['Name'] != 'terminated' and instance.tags[0]['Value'] == 'latency-testing'}

env.hosts = [instance.public_dns_name for instance in instances
             if instance.state['Name'] != 'terminated' and instance.tags[0]['Value'] == 'latency-testing']

env.user = 'ec2-user'
env.key_filename = private_key_file
env.port = 22


def start():
    # ami_id = 'ami-971066f2'
    ami_id = 'ami-60b6c60a'
    # instance_type = 'm1.small'
    instance_type = 't2.micro'
    for subnet in subnets:
        print(pformat(subnet))
        try:
            instance = ec2.create_instances(ImageId=ami_id,
                                            MinCount=1,
                                            MaxCount=1,
                                            KeyName=KEY_PAIR_NAME,
                                            InstanceType=instance_type,
                                            SubnetId=subnet['SubnetId'],
                                            )[0]
        except ClientError as err:
            print(err)

        security_group = ec2.SecurityGroup(instance.security_groups[0]['GroupId'])
        ssh_permission = [permission for permission in security_group.ip_permissions
                          if 'ToPort' in permission and permission['ToPort'] == 22]
        if not ssh_permission:
            security_group.authorize_ingress(IpProtocol='tcp', FromPort=22, ToPort=22, CidrIp='0.0.0.0/0')
        instance.create_tags(Tags=[{'Key': 'Purpose', 'Value': 'latency-testing'}])


@parallel
def install():
    run('sudo yum -y install git python34 python34-pip')
    run('git clone https://github.com/PierreRochard/coinbase-exchange-order-book')
    run('sudo pip-3.4 install -r ~/coinbase-exchange-order-book/testdata/requirements.txt')


@parallel
def test():
    run('python34 ~/coinbase-exchange-order-book/testdata/collectdata.py --m 420')


@parallel
def results():
    get('~/latencies.json', 'latencies_{0}_{1}.json'.format(env.host_string, instance_availability_zones[env.host_string]))


@parallel
def update():
    with cd('~/coinbase-exchange-order-book/'):
        run('git pull')


@parallel
def ssh():
    print(
        'ssh -i /Users/Rochard/src/coinbase-exchange-order-book/keys/coinbase.pem ec2-user@{0}'.format(env.host_string))


@parallel
def terminate():
    for instance in ec2.instances.all():
        if instance.state['Name'] != 'terminated' and instance.tags[0]['Value'] == 'latency-testing':
            instance.terminate()
