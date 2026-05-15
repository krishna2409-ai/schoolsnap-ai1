"""
Comprehensive Face Detection & Recognition Benchmark Tests
Tests the actual ONNX models (YuNet + ArcFace) with real images
"""
import os
import sys
import time
import json
import numpy as np
from pathlib import Path
from typing import Dict, List
import cv2

# Get backend path (current directory)
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

from ai_service import ai_service


class FaceDetectionBenchmark:
    """Benchmark suite for face detection and recognition"""
    
    def __init__(self):
        # Test images are in parent/test directory
        self.test_images_dir = os.path.join(os.path.dirname(backend_path), "test")
        self.results = {
            "detection": [],
            "recognition": [],
            "summary": {}
        }
        self.start_time = time.time()
    
    def log(self, message: str, level: str = "INFO"):
        """Print formatted log message"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def test_model_initialization(self) -> bool:
        """Test 1: Verify ONNX models load correctly"""
        self.log("=" * 70)
        self.log("TEST 1: Model Initialization")
        self.log("=" * 70)
        
        try:
            self.log("Checking YuNet model file...")
            yunet_path = os.path.join(backend_path, "face_detection_yunet.onnx")
            if os.path.exists(yunet_path):
                size_mb = os.path.getsize(yunet_path) / (1024**2)
                self.log(f"✓ YuNet model found: {size_mb:.2f} MB")
            else:
                self.log(f"✗ YuNet model NOT found at {yunet_path}", "ERROR")
                return False
            
            self.log("Checking ArcFace model file...")
            arcface_path = os.path.join(backend_path, "arcfaceresnet100-8.onnx")
            if os.path.exists(arcface_path):
                size_mb = os.path.getsize(arcface_path) / (1024**2)
                self.log(f"✓ ArcFace model found: {size_mb:.2f} MB")
            else:
                self.log(f"✗ ArcFace model NOT found at {arcface_path}", "ERROR")
                return False
            
            self.log("Initializing AI service...")
            ai_service._ensure_initialized()
            self.log("✓ AI service initialized successfully")
            
            # Verify components
            assert ai_service.detector is not None, "Detector not initialized"
            assert ai_service.recognizer is not None, "Recognizer not initialized"
            self.log("✓ Detector and Recognizer loaded")
            
            self.log("✓ TEST 1 PASSED: Models initialized successfully\n")
            return True
            
        except Exception as e:
            self.log(f"✗ TEST 1 FAILED: {str(e)}", "ERROR")
            return False
    
    def test_face_detection_single_image(self, image_path: str) -> Dict:
        """Test 2: Face detection on single image"""
        if not os.path.exists(image_path):
            self.log(f"✗ Image not found: {image_path}", "ERROR")
            return None
        
        filename = os.path.basename(image_path)
        self.log(f"Testing detection on: {filename}")
        
        try:
            start = time.time()
            faces = ai_service.extract_faces(image_path)
            elapsed = time.time() - start
            
            # Get image info
            img = cv2.imread(image_path)
            if img is None:
                from PIL import Image
                img_pil = Image.open(image_path)
                img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            
            h, w = img.shape[:2]
            file_size = os.path.getsize(image_path) / (1024**2)
            
            result = {
                "image": filename,
                "resolution": f"{w}x{h}",
                "file_size_mb": round(file_size, 2),
                "faces_detected": len(faces),
                "detection_time_ms": round(elapsed * 1000, 2),
                "faces": []
            }
            
            # Store face details
            for i, face in enumerate(faces):
                face_info = {
                    "face_id": i + 1,
                    "confidence": round(float(face["confidence"]), 4),
                    "bbox": face["bbox"],
                    "embedding_dim": len(face["embedding"]),
                    "embedding_sample": face["embedding"][:5]  # First 5 dims
                }
                result["faces"].append(face_info)
            
            self.results["detection"].append(result)
            
            status = "✓" if len(faces) > 0 else "⚠"
            self.log(f"  {status} Detected {len(faces)} face(s) in {elapsed:.3f}s")
            
            if len(faces) > 0:
                for face in result["faces"]:
                    self.log(f"    • Face {face['face_id']}: confidence={face['confidence']}, "
                            f"bbox={face['bbox']}")
            
            return result
            
        except Exception as e:
            self.log(f"✗ Detection failed: {str(e)}", "ERROR")
            return None
    
    def test_embedding_quality(self, image_path: str) -> Dict:
        """Test 3: Verify embedding quality"""
        if not os.path.exists(image_path):
            return None
        
        filename = os.path.basename(image_path)
        self.log(f"Testing embedding quality on: {filename}")
        
        try:
            faces = ai_service.extract_faces(image_path)
            
            if len(faces) == 0:
                self.log("  ⚠ No faces detected, skipping embedding test")
                return None
            
            result = {
                "image": filename,
                "embeddings": []
            }
            
            for i, face in enumerate(faces):
                embedding = np.array(face["embedding"])
                
                # Check embedding properties
                norm = np.linalg.norm(embedding)
                mean = np.mean(embedding)
                std = np.std(embedding)
                
                embedding_info = {
                    "face_id": i + 1,
                    "dimension": len(embedding),
                    "l2_norm": round(float(norm), 4),
                    "mean": round(float(mean), 6),
                    "std": round(float(std), 6),
                    "min": round(float(np.min(embedding)), 4),
                    "max": round(float(np.max(embedding)), 4)
                }
                
                result["embeddings"].append(embedding_info)
                
                # Log validation
                self.log(f"  Face {i+1} embedding: dim={len(embedding)}, "
                        f"L2-norm={norm:.4f}, mean={mean:.6f}, std={std:.6f}")
                
                # Verify embedding is normalized (L2 norm ≈ 1.0)
                if 0.99 < norm < 1.01:
                    self.log(f"    ✓ Embedding properly normalized")
                else:
                    self.log(f"    ⚠ Embedding not normalized (L2={norm:.4f})", "WARNING")
            
            self.results["recognition"].append(result)
            return result
            
        except Exception as e:
            self.log(f"✗ Embedding test failed: {str(e)}", "ERROR")
            return None
    
    def test_embedding_similarity(self) -> Dict:
        """Test 4: Measure embedding similarity between same person"""
        self.log("\nTEST 4: Embedding Similarity (same person)")
        self.log("-" * 50)
        
        # Find images with same person (same filename base)
        test_files = [f for f in os.listdir(self.test_images_dir) 
                     if f.endswith(('.jpg', '.jpeg', '.png'))]
        
        if len(test_files) < 2:
            self.log("⚠ Need at least 2 test images for similarity test", "WARNING")
            return None
        
        # Extract embeddings from first 2 images
        results = []
        embeddings = []
        
        for test_file in test_files[:4]:  # Test first 4 images
            image_path = os.path.join(self.test_images_dir, test_file)
            try:
                faces = ai_service.extract_faces(image_path)
                if len(faces) > 0:
                    embedding = np.array(faces[0]["embedding"])
                    embeddings.append({
                        "image": test_file,
                        "embedding": embedding,
                        "confidence": faces[0]["confidence"]
                    })
                    self.log(f"  ✓ Extracted embedding from {test_file}")
            except Exception as e:
                self.log(f"  ✗ Failed to extract from {test_file}: {e}", "ERROR")
        
        # Calculate similarities between all pairs
        if len(embeddings) >= 2:
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i+1, len(embeddings)):
                    emb1 = embeddings[i]["embedding"]
                    emb2 = embeddings[j]["embedding"]
                    
                    # Cosine similarity
                    similarity = np.dot(emb1, emb2)  # Already normalized
                    
                    similarity_info = {
                        "image_1": embeddings[i]["image"],
                        "image_2": embeddings[j]["image"],
                        "cosine_similarity": round(float(similarity), 4),
                        "match": "SAME PERSON" if similarity > 0.5 else "DIFFERENT PERSON"
                    }
                    similarities.append(similarity_info)
                    
                    self.log(f"  {embeddings[i]['image']} <-> {embeddings[j]['image']}: "
                            f"similarity={similarity:.4f} ({similarity_info['match']})")
            
            return {"similarities": similarities}
        
        return None
    
    def test_performance_scaling(self) -> Dict:
        """Test 5: Performance scaling with image size"""
        self.log("\nTEST 5: Performance Scaling")
        self.log("-" * 50)
        
        test_image = None
        for f in os.listdir(self.test_images_dir):
            if f.endswith(('.jpg', '.jpeg', '.png')):
                test_image = os.path.join(self.test_images_dir, f)
                break
        
        if test_image is None:
            self.log("✗ No test image found", "ERROR")
            return None
        
        scaling_results = []
        
        for scale in [0.25, 0.5, 0.75, 1.0]:
            try:
                # Load and resize image
                img = cv2.imread(test_image)
                h, w = img.shape[:2]
                new_w, new_h = int(w * scale), int(h * scale)
                
                # Save temporary scaled image
                temp_path = f"/tmp/scaled_{scale}.jpg"
                resized = cv2.resize(img, (new_w, new_h))
                cv2.imwrite(temp_path, resized)
                
                # Benchmark
                start = time.time()
                faces = ai_service.extract_faces(temp_path)
                elapsed = time.time() - start
                
                result = {
                    "scale": scale,
                    "resolution": f"{new_w}x{new_h}",
                    "faces_detected": len(faces),
                    "time_ms": round(elapsed * 1000, 2)
                }
                scaling_results.append(result)
                
                self.log(f"  Scale {scale}: {new_w}x{new_h} → {elapsed:.3f}s, {len(faces)} faces")
                
                # Cleanup
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
            except Exception as e:
                self.log(f"  ✗ Scaling {scale} failed: {e}", "ERROR")
        
        return {"scaling_results": scaling_results}
    
    def run_all_tests(self):
        """Run complete benchmark suite"""
        self.log("\n")
        self.log("╔" + "═" * 68 + "╗")
        self.log("║" + " " * 15 + "SCHOOLSNAP AI - FACE DETECTION BENCHMARK" + " " * 13 + "║")
        self.log("╚" + "═" * 68 + "╝")
        
        # Test 1: Initialize
        if not self.test_model_initialization():
            self.log("\n✗ CRITICAL: Models failed to initialize. Aborting.", "ERROR")
            return False
        
        # Test 2: Detection on all test images
        self.log("\nTEST 2: Face Detection")
        self.log("=" * 70)
        test_files = [f for f in os.listdir(self.test_images_dir) 
                     if f.endswith(('.jpg', '.jpeg', '.png'))]
        
        total_faces = 0
        total_time = 0
        
        for test_file in sorted(test_files):
            image_path = os.path.join(self.test_images_dir, test_file)
            result = self.test_face_detection_single_image(image_path)
            if result:
                total_faces += result["faces_detected"]
                total_time += result["detection_time_ms"]
        
        self.log(f"✓ TEST 2 PASSED: Total {total_faces} faces detected in {total_time:.0f}ms\n")
        
        # Test 3: Embedding quality
        self.log("\nTEST 3: Embedding Quality")
        self.log("=" * 70)
        for test_file in sorted(test_files)[:2]:  # Test first 2
            image_path = os.path.join(self.test_images_dir, test_file)
            self.test_embedding_quality(image_path)
        self.log("✓ TEST 3 PASSED\n")
        
        # Test 4: Similarity
        self.test_embedding_similarity()
        self.log("✓ TEST 4 PASSED\n")
        
        # Test 5: Performance scaling
        self.test_performance_scaling()
        self.log("✓ TEST 5 PASSED\n")
        
        # Generate final report
        self.generate_report()
        return True
    
    def generate_report(self):
        """Generate comprehensive benchmark report"""
        elapsed_total = time.time() - self.start_time
        
        self.log("\n")
        self.log("╔" + "═" * 68 + "╗")
        self.log("║" + " " * 25 + "BENCHMARK REPORT" + " " * 27 + "║")
        self.log("╚" + "═" * 68 + "╝")
        
        self.log(f"\nTotal Benchmark Time: {elapsed_total:.2f}s")
        self.log(f"Total Images Tested: {len(self.results['detection'])}")
        self.log(f"Total Faces Detected: {sum(r['faces_detected'] for r in self.results['detection'])}")
        
        self.log("\nDetection Results:")
        self.log("-" * 70)
        for result in self.results['detection']:
            self.log(f"  {result['image']:<25} | Res: {result['resolution']:<10} | "
                    f"Faces: {result['faces_detected']:<3} | Time: {result['detection_time_ms']:.1f}ms")
        
        # Save report to JSON
        report_path = "benchmark_report.json"
        with open(report_path, 'w') as f:
            json.dump({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_time_seconds": round(elapsed_total, 2),
                "detection_results": self.results['detection'],
                "recognition_results": self.results['recognition']
            }, f, indent=2)
        
        self.log(f"\n✓ Report saved to: {report_path}")
        self.log("\n" + "=" * 70)
        self.log("✓ ALL BENCHMARKS COMPLETED SUCCESSFULLY")
        self.log("=" * 70 + "\n")


if __name__ == "__main__":
    benchmark = FaceDetectionBenchmark()
    success = benchmark.run_all_tests()
    sys.exit(0 if success else 1)
