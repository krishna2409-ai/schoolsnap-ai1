import os
import cv2
import numpy as np
from typing import List, Optional

class AIService:
    def __init__(self):
        self._initialized = False
        self.detector = None
        self.recognizer = None
        
        # Paths to models in backend folder or parent container folder
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.parent_dir = os.path.dirname(self.base_dir)
        
        # Check parent folder first (container root) then fall back to base_dir
        yunet_root = os.path.join(self.parent_dir, "face_detection_yunet.onnx")
        if os.path.exists(yunet_root):
            self.yunet_path = yunet_root
        else:
            self.yunet_path = os.path.join(self.base_dir, "face_detection_yunet.onnx")
            
        arcface_root = os.path.join(self.parent_dir, "arcfaceresnet100-8.onnx")
        if os.path.exists(arcface_root):
            self.arcface_path = arcface_root
        else:
            self.arcface_path = os.path.join(self.base_dir, "arcfaceresnet100-8.onnx")

    def _ensure_initialized(self, width: int = 320, height: int = 320):
        # Smart bypass default: True on Railway/Docker, False in local dev
        is_cloud = os.getenv("RAILWAY_STATIC_URL") or os.getenv("RAILWAY_SERVICE_ID") or os.path.exists("/.dockerenv")
        default_bypass = "true" if is_cloud else "false"
        if os.getenv("BYPASS_HEAVY_AI", default_bypass).lower() == "true":
            print(f"[AI] Bypassing heavy ONNX pipeline initialization (BYPASS_HEAVY_AI={default_bypass} by default)")
            self._initialized = True
            return

        if not self._initialized:
            print(f"[AI] Initializing ONNX pipeline (YuNet + ArcFace)...")
            
            # Additional check: let's try root/app files directly if we still see errors
            if not os.path.exists(self.yunet_path):
                alt_yunet = "/app/face_detection_yunet.onnx"
                if os.path.exists(alt_yunet):
                    self.yunet_path = alt_yunet
                else:
                    raise FileNotFoundError(f"Missing YuNet model at {self.yunet_path}")
                    
            if not os.path.exists(self.arcface_path):
                alt_arcface = "/app/arcfaceresnet100-8.onnx"
                if os.path.exists(alt_arcface):
                    self.arcface_path = alt_arcface
                else:
                    raise FileNotFoundError(f"Missing ArcFace model at {self.arcface_path}")

            # Initialize Detector
            self.detector = cv2.FaceDetectorYN.create(
                model=self.yunet_path,
                config="",
                input_size=(width, height),
                score_threshold=0.6,
                nms_threshold=0.3,
                top_k=5000
            )
            
            # Initialize Recognizer
            self.recognizer = cv2.FaceRecognizerSF.create(
                model=self.arcface_path,
                config=""
            )
            
            self._initialized = True
            print("[AI] ONNX pipeline initialized successfully.")

    def extract_faces(self, image_path: str, max_dimension: int = 1280) -> List[dict]:
        """
        Detects faces and generates 512d embeddings using YuNet and ArcFace ONNX.
        """
        is_cloud = os.getenv("RAILWAY_STATIC_URL") or os.getenv("RAILWAY_SERVICE_ID") or os.path.exists("/.dockerenv")
        default_bypass = "true" if is_cloud else "false"
        if os.getenv("BYPASS_HEAVY_AI", default_bypass).lower() == "true":
            print(f"[AI] Bypassing face extraction for {image_path} (BYPASS_HEAVY_AI={default_bypass} by default).")
            return []
        # Read image
        try:
            from PIL import Image, ImageOps
            pil_img = Image.open(image_path)
            pil_img = ImageOps.exif_transpose(pil_img)
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception:
            img = cv2.imread(image_path)
            
        if img is None:
            print(f"[AI] Error: could not read {image_path}")
            return []

        h, w = img.shape[:2]
        
        # Scaling logic for detector performance and accuracy
        # Usually we want a balance. 1280 is a good max dimension for group photos.
        scale = 1.0
        if max(h, w) > max_dimension:
            scale = max_dimension / max(h, w)
            img_detect = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            img_detect = img.copy()
            
        dh, dw = img_detect.shape[:2]
        self._ensure_initialized(dw, dh)
        self.detector.setInputSize((dw, dh))
        
        _, faces = self.detector.detect(img_detect)
        
        results = []
        if faces is not None:
            for face in faces:
                # 1. Get components from YuNet detection format (15 values per face)
                # [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rm, y_rm, x_lm, y_lm, confidence]
                bbox = face[0:4].astype(int)
                landmarks = face[4:14].reshape(5, 2)
                confidence = float(face[14])
                
                # 2. Skip low confidence or tiny faces
                if confidence < 0.6:
                    continue
                
                # Filter by actual face size in original image
                orig_w = int(bbox[2] / scale)
                orig_h = int(bbox[3] / scale)
                if orig_w < 35 or orig_h < 35:
                    continue

                # 3. Align and extract embedding
                # ArcFace needs 112x112 aligned image
                try:
                    aligned_face = self.recognizer.alignCrop(img_detect, face)
                    embedding = self.recognizer.feature(aligned_face) # returns 512d vector
                    
                    # Normalize embedding for Cosine similarity
                    emb_arr = embedding[0].flatten().astype(np.float32)
                    norm = np.linalg.norm(emb_arr)
                    if norm > 0:
                        emb_arr = emb_arr / norm
                    
                    results.append({
                        "embedding": emb_arr.tolist(),
                        "bbox": [int(bbox[0]/scale), int(bbox[1]/scale), 
                                 int((bbox[0]+bbox[2])/scale), int((bbox[1]+bbox[3])/scale)],
                        "landmarks": [
                            [int(point[0] / scale), int(point[1] / scale)]
                            for point in landmarks
                        ],
                        "confidence": confidence
                    })
                except Exception as e:
                    print(f"[AI] Recognition failed for a face in {image_path}: {e}")

        return results

    def generate_watermarked_preview(self, image_path: str, output_path: str, 
                                      watermark_text: str = "SCHOOLSNAP AI",
                                      max_preview_width: int = 800):
        """
        Generates a low-resolution watermarked preview image using OpenCV.
        """
        try:
            from PIL import Image, ImageOps
            pil_img = Image.open(image_path)
            pil_img = ImageOps.exif_transpose(pil_img)
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception:
            img = cv2.imread(image_path)
            
        if img is None:
            return False
            
        # Resize to preview size
        height, width = img.shape[:2]
        if width > max_preview_width:
            scale = max_preview_width / width
            img = cv2.resize(img, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        
        h, w = img.shape[:2]
        overlay = img.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Calculate font scale based on image size
        font_scale = max(0.5, w / 400)
        thickness = max(1, int(font_scale * 2))
        
        # Draw multiple watermark lines across the image
        text_size = cv2.getTextSize(watermark_text, font, font_scale, thickness)[0]
        
        # Diagonal watermarks across the image
        for y_offset in range(-h, h * 2, text_size[1] * 4):
            for x_offset in range(-w, w * 2, text_size[0] + 50):
                cv2.putText(overlay, watermark_text, (x_offset, y_offset), 
                           font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
        
        # Blend overlay
        alpha = 0.15
        cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
        
        # Add a semi-transparent banner at the bottom
        banner_h = max(30, int(h * 0.06))
        img[h - banner_h:h, :] = cv2.addWeighted(
            img[h - banner_h:h, :], 0.4,
            np.full_like(img[h - banner_h:h, :], (30, 30, 30)), 0.6, 0
        )
        small_scale = max(0.3, font_scale * 0.4)
        cv2.putText(img, "PREVIEW - Purchase for full resolution", 
                   (10, h - banner_h // 3), font, small_scale, (200, 200, 200), 1, cv2.LINE_AA)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return True


# Singleton instance
ai_service = AIService()
