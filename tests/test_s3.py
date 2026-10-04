import boto3

s3 = boto3.client(
    "s3",
    region_name="us-east-1"
)

response = s3.get_object(
    Bucket="carebot-camera-mhacks",
    Key="camera/five_bottles.jpg"
)

image_bytes = response["Body"].read()

print("Successfully got image from S3!")
print("Image size:", len(image_bytes), "bytes")