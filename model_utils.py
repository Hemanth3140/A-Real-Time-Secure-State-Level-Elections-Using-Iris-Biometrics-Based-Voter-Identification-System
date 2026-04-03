import numpy as np
import cv2
import os
import pickle
from tensorflow.keras.models import Sequential, model_from_json
from tensorflow.keras.layers import Dense, Dropout, Flatten, Conv2D, MaxPooling2D
from tensorflow.keras.utils import to_categorical
from tensorflow.keras import backend as K

class IrisModel:
    def __init__(self, model_dir='model'):
        self.model_dir = model_dir
        self.model = None
        self.accuracy = 0
        self.history = None
        self.load_model()

    def get_iris_features(self, image_path):
        img = cv2.imread(image_path, 0)
        if img is None:
            return None
            
        img = cv2.medianBlur(img, 5)
        cimg = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        circles = cv2.HoughCircles(img, cv2.HOUGH_GRADIENT, 1, 10, param1=63, param2=70, minRadius=0, maxRadius=0)
        
        crop = None
        if circles is not None:
            height, width = img.shape
            mask = np.zeros((height, width), np.uint8)
            for i in circles[0, :]:
                cv2.circle(cimg, (int(i[0]), int(i[1])), int(i[2]), (0, 0, 0))
                cv2.circle(mask, (int(i[0]), int(i[1])), int(i[2]), (255, 255, 255), thickness=0)
                
                masked_data = cv2.bitwise_and(cimg, cimg, mask=mask)
                _, thresh = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    x, y, w, h = cv2.boundingRect(contours[0])
                    crop = img[y:y+h, x:x+w]
                    # Save a temp file if needed, mimicking original behavior or just return
                    # For prediction we need the cropped image
                    break
        
        # If no circles found or cropping failed, use original or handle error
        # The original code just appends to miss and returns cv2.imread("test.png") which might be stale
        # We will return the cropped image if found, else None
        return crop

    def load_model(self):
        json_path = os.path.join(self.model_dir, 'model.json')
        weights_path = os.path.join(self.model_dir, 'model_weights.h5')
        history_path = os.path.join(self.model_dir, 'history.pckl')

        if os.path.exists(json_path) and os.path.exists(weights_path):
            try:
                with open(json_path, "r") as json_file:
                    loaded_model_json = json_file.read()
                    self.model = model_from_json(loaded_model_json)
                self.model.load_weights(weights_path)
                print("Model loaded from disk")
                
                if os.path.exists(history_path):
                    with open(history_path, 'rb') as f:
                        data = pickle.load(f)
                        acc = data['accuracy']
                        self.accuracy = acc[-1] * 100
                        self.history = data
            except Exception as e:
                print(f"Error loading model: {e}")
                self.model = None

    def train_model(self):
        x_path = os.path.join(self.model_dir, 'X.txt.npy')
        y_path = os.path.join(self.model_dir, 'Y.txt.npy')
        
        if not os.path.exists(x_path) or not os.path.exists(y_path):
            return "Dataset not found in model directory."

        X_train = np.load(x_path)
        Y_train = np.load(y_path)
        
        # Model Architecture
        model = Sequential()
        model.add(Conv2D(32, (3, 3), input_shape=(64, 64, 3), activation='relu'))
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Conv2D(32, (3, 3), activation='relu'))
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Flatten())
        model.add(Dense(256, activation='relu'))
        model.add(Dense(108, activation='softmax')) # Original had 108 output dim
        
        model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
        
        hist = model.fit(X_train, Y_train, batch_size=16, epochs=60, shuffle=True, verbose=2)
        
        self.model = model
        
        # Save
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
            
        # model.save_weights(os.path.join(self.model_dir, 'model_weights.h5'))
        model.save_weights(os.path.join(self.model_dir, 'model_weights.weights.h5'))
        model.save(os.path.join(self.model_dir, 'model.h5'))
        with open(os.path.join(self.model_dir, 'model.json'), "w") as json_file:
            json_file.write(model.to_json())
            
        with open(os.path.join(self.model_dir, 'history.pckl'), 'wb') as f:
            pickle.dump(hist.history, f)
            
        self.history = hist.history
        self.accuracy = hist.history['accuracy'][-1] * 100
        
        return f"Training completed. Accuracy: {self.accuracy:.2f}%"

    def predict(self, image_path):
        if self.model is None:
            return None, "Model not loaded"
            
        crop = self.get_iris_features(image_path)
        
        if crop is None:
             # Fallback: try to load the image directly if cropping failed (maybe it's already cropped?)
             # Or just use the original image resized
             img = cv2.imread(image_path)
             if img is None:
                 return None, "Image load failed"
             # Resize to what the model expects? 
             # The original code expects getIrisFeatures to return an image, calls it 'image'.
             # Then it does:
             # img = cv2.resize(image, (64,64))
             # So we need to ensure we have an image content here.
             # If get_iris_features returned None (no circle), the original code used 'test.png' from previous run or crashed?
             # Original: count = count + 1; miss.append(image); return cv2.imread("test.png")
             # This is risky. We will handle gracefully.
             # Let's assume if crop fails, we can't predict reliably, but we can try using the whole image.
             pass
        else:
             img = crop

        if img is None: # Double check
             return None, "Initial processing failed"

        try:
            img_resized = cv2.resize(img, (64, 64))
            
            # If the image is grayscale (from crop), we need to make it 3 channels if model expects 3
            # Original model input shape: (64, 64, 3)
            # getIrisFeatures reads as grayscale (0) -> cimg is BGR. 
            # But the crop is from 'img' which is grayscale?
            # Original: code line 34: img = cv2.imread(image,0) # grayscale
            # ...
            # line 51: crop = img[y:y+h,x:x+w] # crop from grayscale
            # line 53: cv2.imwrite("test.png",crop)
            # line 57: return cv2.imread("test.png") # This reads as COLOR (BGR) by default because flag is missing (default 1)
            # So the returned image is BGR (3 channels).
            # My get_iris_features returns 'crop' which is from grayscale 'img'.
            # So I should convert it back to BGR to match original behavior.
            
            if len(img_resized.shape) == 2:
                img_resized = cv2.cvtColor(img_resized, cv2.COLOR_GRAY2BGR)
            
            im2arr = np.array(img_resized)
            im2arr = im2arr.reshape(1, 64, 64, 3)
            img_final = im2arr.astype('float32')
            img_final = img_final / 255
            
            preds = self.model.predict(img_final)
            predict_id = np.argmax(preds) + 1
            return predict_id, None
            
        except Exception as e:
            return None, str(e)

model_instance = IrisModel()
