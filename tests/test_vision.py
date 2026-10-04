from tools.vision import inspect_scene

# test specifically says thers a target, but how would agent know what target means or what too set as target?
# because right now we're only testing, so we manually set target
# can we test that it would be able to parse target from a prompt then?
# why arent we just simply prompting with an image?
# because eventually the agent will decide the target itself from the prompt 
# e.g. "where is my medicaition bottle?" sets target to: medication bottle
result = inspect_scene(
    target="water",
    image_path="test_images/kitchen.jpg"
)

print(result)