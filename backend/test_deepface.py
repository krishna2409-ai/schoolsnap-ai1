from deepface import DeepFace
import sys
import os

image_path = '../test/Highlights/WhatsApp Image 2026-03-20 at 6.17.16 PM.jpeg'
if not os.path.exists(image_path):
    print('File not found')
    sys.exit(1)

print('Testing DeepFace initialization...')
try:
    res = DeepFace.represent(img_path=image_path, model_name='GhostFaceNet', detector_backend='retinaface', enforce_detection=False)
    print(f'Success! Detected {len(res)} faces.')
except Exception as e:
    print('Failed:', e)
