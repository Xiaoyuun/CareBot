from tools.vision import inspect_scene

# if input was not target, but a prompt, then we would need to parse the target from the prompt first, and then pass it to inspect_scene
# only test for def inspect_scene(prompt, image_path):, not currentdef inspect_scene(target, image_path):

user_request = "Can you find my water bottle?"

target = extract_target(user_request)

print(target)
# water bottle

result = inspect_scene(
    target=target,
    image_path="test_images/bottle1.jpg"
)

print(result)