import boto3
import sys
import datetime
import time

def get_instance_name(ec2_client, instance_id):
    """Retrieve the instance name from tags."""
    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    reservations = response.get("Reservations", [])
    for reservation in reservations:
        for instance in reservation.get("Instances", []):
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    return tag["Value"]
    return "UnknownInstance"

def get_unique_ami_name(ec2_client, base_name):
    """Generate a unique AMI name by adding a revision number if needed."""
    existing_amis = ec2_client.describe_images(Owners=["self"])["Images"]
    
    existing_names = {ami["Name"] for ami in existing_amis}
    unique_name = base_name
    revision = 1

    while unique_name in existing_names:
        unique_name = f"{base_name}_rev{revision}"
        revision += 1

    return unique_name

def create_ami_backup(instance_id, region):
    """Create an AMI backup of an instance without rebooting and wait for it to be available."""
    ec2_client = boto3.client("ec2", region_name=region)
    
    instance_name = get_instance_name(ec2_client, instance_id)
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    base_ami_name = f"{instance_name}_{date_str}_{region}"
    
    # Ensure AMI name is unique
    ami_name = get_unique_ami_name(ec2_client, base_ami_name)

    print(f"Creating AMI backup for instance {instance_id} with name: {ami_name}...")
    
    response = ec2_client.create_image(
        InstanceId=instance_id,
        Name=ami_name,
        NoReboot=True
    )
    
    ami_id = response["ImageId"]
    print(f"AMI {ami_id} and name {ami_name} creation started... Waiting for it to become available.")

    # Custom wait logic instead of waiter
    max_attempts = 270  # 40 attempts (~20 minutes max)
    delay_seconds = 10  # Wait 30 seconds between each attempt

    for attempt in range(max_attempts):
        time.sleep(delay_seconds)  # Wait before next check
        try:
            image_status = ec2_client.describe_images(ImageIds=[ami_id])["Images"][0]["State"]
            print(f"Attempt {attempt+1}/{max_attempts}: AMI {ami_id} status: {image_status}")
            if image_status == "available":
                print(f"✅ AMI {ami_id} is now available with name: {ami_name}")
                return ami_id
        except Exception as e:
            print(f"⚠️ Error checking AMI status (Attempt {attempt+1}): {e}")

    print(f"❌ AMI {ami_id} did not become available within the timeout period.")
    return None

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_ami_backup.py <instance-id> <region>")
        sys.exit(1)
    
    instance_id = sys.argv[1]
    region = sys.argv[2]
    
    create_ami_backup(instance_id, region)
