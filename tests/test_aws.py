import boto3
import json


# Connect to Amazon Bedrock
bedrock = boto3.client(
   "bedrock-runtime",
   region_name="us-east-1"
)


# for camera "image" storage, we will use s3 to store the image and then
# Get the simulated camera image from S3,
# then pass the image bytes to Bedrock.
s3 = boto3.client(
   "s3",
   region_name="us-east-1"
)


BUCKET_NAME = "carebot-camera-mhacks"


# CareBot or another specialist agent determines WHAT object to search for.
# Vision is only responsible for determining whether that target appears
# in the current camera frame and where it is located.
def inspect_scene(target, image_key):
   """
   Look at an image and determine where the target object is.


   Example:
       inspect_scene("water bottle", "camera.jpg")
   """


   # old
   # 1. Read the image from your computer
   #with open(image_path, "rb") as f:
   #    image_bytes = f.read()
  
   # 1. Get simulated camera image from S3
   response = s3.get_object(
       Bucket=BUCKET_NAME,
       Key=image_key
   )


   image_bytes = response["Body"].read()




   # 2. Tell the vision model what we want it to do
   prompt = f"""
   You are the vision system for an assistive robot.


   The robot is searching for: {target}


   Analyze the provided image.


   Return ONLY JSON in this format:


   {{
       "target_visible": true or false,
       "direction": "left" | "center" | "right" | "unknown",
       "description": "short description"
   }}
   """
   # , specific to the target, of what you see in the image, and where the target is located in relation to the robot's current position, and any other relevant information that might help the robot find the target.
   # 3. Send the image + prompt to a multimodal model through Bedrock
   # uses bedrocks converse api - accepts text and images
   response = bedrock.converse(
       modelId="amazon.nova-lite-v1:0",


       messages=[
           {
               "role": "user",
               "content": [
                   {
                       "image": {
                           "format": "jpeg",
                           "source": {
                               "bytes": image_bytes
                           }
                       }
                   },
                   {
                       "text": prompt
                   }
               ]
           }
       ]
   )


   # 4. Get the model's response
   response_text = response["output"]["message"]["content"][0]["text"]


   # 5. Convert JSON text into a Python dictionary
   result = json.loads(response_text)


   return result




if __name__ == "__main__":
   result = inspect_scene(
       "water bottle",
       "camera/five_bottles.jpg"
   )


   print(result)
