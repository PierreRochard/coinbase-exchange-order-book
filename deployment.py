from datetime import datetime
import time
import os

from dateutil.tz import tzlocal
import paramiko
from boto3.session import Session

from aws_config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, REGION, KEY_PAIR_NAME

session = Session(aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                  region_name=REGION)


def deploy():
    # Amazon Linux AMI PV Instance Store 64-bit
    ami_id = 'ami-971066f2'

    instance_type = 'm1.small'

    prices = {'m1.small': 0.044}

    ec2 = session.resource('ec2')
    client = session.client('ec2')

    private_key_file = os.path.abspath('keys/{0}.pem'.format(KEY_PAIR_NAME))

    print(private_key_file)
    if not os.path.isfile(private_key_file):
        print('Creating new keys')
        key = client.create_key_pair(KeyName=KEY_PAIR_NAME)
        with open(private_key_file, 'w') as f:
            f.write(key['KeyMaterial'])

    instances = [instance for instance in ec2.instances.all() if instance.state['Name'] != 'terminated']

    if not instances:
        ec2.create_instances(ImageId=ami_id,
                             MinCount=1,
                             MaxCount=1,
                             KeyName=KEY_PAIR_NAME,
                             InstanceType=instance_type)

    while not [instance for instance in ec2.instances.all() if instance.state['Name'] == 'running']:
        time.sleep(5)

    instance = instances[0]
    print('ssh -i {0} ec2-user@{1}'.format(private_key_file, instance.public_ip_address))

    print(instance.id, instance.instance_type, instance.state,
          round((datetime.now(tzlocal()) - instance.launch_time).seconds / 60 / 60 * prices[instance.instance_type], 3),
          instance.public_dns_name, instance.public_ip_address)

    print(instance.security_groups[0]['GroupId'])
    security_group = ec2.SecurityGroup(instance.security_groups[0]['GroupId'])
    ssh_permission = [permission for permission in security_group.ip_permissions
                      if 'ToPort' in permission and permission['ToPort'] == 22]
    if not ssh_permission:
        security_group.authorize_ingress(IpProtocol='tcp', FromPort=22, ToPort=22, CidrIp='0.0.0.0/0')

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(instance.public_ip_address, username='ec2-user', key_filename=private_key_file)
    stdin, stdout, stderr = ssh.exec_command("sudo yum update -y; sudo yum -y install git python34 python34-pip gcc python34-devel;")
    if len(stderr.read().splitlines()) > 0:
        print(stderr.read().splitlines())
        print('ssh -i {0} ec2-user@{1}'.format(private_key_file, instance.public_ip_address))
        print('sudo nano /etc/sudoers')
        print('add a # in front of Defaults requiretty to fix this issue')
        return False
    stdin.flush()
    data = stdout.read().splitlines()
    for line in data:
        print(line)
    stdin, stdout, stderr = ssh.exec_command("git clone https://github.com/PierreRochard/coinbase-exchange-order-book.git")
    stdin.flush()
    if stderr:
        print('Error')
        print(stderr.read().splitlines())
        stdin, stdout, stderr = ssh.exec_command("cd coinbase-exchange-order-book; git pull;")
        stdin.flush()
        if stderr:
            print('Error')
            print(stderr.read().splitlines())
        data = stdout.read().splitlines()
        for line in data:
            print(line)
    data = stdout.read().splitlines()
    for line in data:
        print(line)
    stdin, stdout, stderr = ssh.exec_command("sudo pip-3.4 install -r coinbase-exchange-order-book/requirements.txt")
    stdin.flush()
    if stderr:
        print('Error')
        print(stderr.read().splitlines())
    data = stdout.read().splitlines()
    for line in data:
        print(line)
    sftp = ssh.open_sftp()
    local_config = os.path.abspath('coinbase_config.py')
    remote_config = '/home/ec2-user/coinbase-exchange-order-book/coinbase_config.py'
    sftp.put(local_config, remote_config)
    local_config = os.path.abspath('twitter_config.py')
    remote_config = '/home/ec2-user/coinbase-exchange-order-book/twitter_config.py'
    sftp.put(local_config, remote_config)
    sftp.close()

    # sudo easy_install supervisor
    # sudo cp supervisor.conf /etc/supervisor.conf
    # supervisord -c /etc/supervisord.conf
    # supervisorctl reload

    stdin, stdout, stderr = ssh.exec_command("supervisorctl status; supervisorctl reread; supervisorctl update; supervisorctl restart all; supervisorctl status")
    stdin.flush()
    if stderr:
        print('Error')
        print(stderr.read().splitlines())
    data = stdout.read().splitlines()
    for line in data:
        print(line)
    ssh.close()

if __name__ == '__main__':
    deploy()
