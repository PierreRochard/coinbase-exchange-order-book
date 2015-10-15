from datetime import datetime
import time
import os

from dateutil.tz import tzlocal
import paramiko
from boto3.session import Session

from config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, REGION, KEY_PAIR_NAME

session = Session(aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                  region_name=REGION)


# Amazon Linux AMI PV Instance Store 64-bit
ami_id = 'ami-971066f2'

instance_type = 't2.micro'

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
                         InstanceType='m1.small')


while not [instance for instance in ec2.instances.all() if instance.state['Name'] == 'running']:
    time.sleep(5)

# Make sure you Edit inbound rules for the Security Group the instance is running on to allow
# SSH connections
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

for instance in [instance for instance in ec2.instances.all() if instance.state['Name'] == 'running']:
    print(instance.id, instance.instance_type, instance.state,
          round((datetime.now(tzlocal()) - instance.launch_time).seconds / 60 / 60 * prices[instance.instance_type], 3),
          instance.public_dns_name, instance.public_ip_address)
    ssh.connect(instance.public_ip_address,
                username='ec2-user',
                key_filename=private_key_file)
    # "sudo yum -y install git python34 python34-pip gcc python34-devel;"
    stdin, stdout, stderr = ssh.exec_command("git clone https://github.com/PierreRochard/coinbase-exchange-order-book.git")
    # sudo pip-3.4 install -r requirements.txt
    print(stderr.read().splitlines())
    stdin.flush()
    data = stdout.read().splitlines()
    for line in data:
        print(line)
    sftp = ssh.open_sftp()
    local_config = os.path.abspath('config.py')
    remote_config = '/home/ec2-user/coinbase-exchange-order-book/config.py'
    sftp.put(local_config, remote_config)
    sftp.close()
    ssh.close()
