import base64
import io
import unittest
from unittest.mock import patch
from PIL import Image
import maintenance
import vision

class VisionAdapterTests(unittest.TestCase):
    def test_missing_model_does_not_report_ready(self):
        with patch.object(vision,'YOLO_PATH',''),patch.object(maintenance,'VISION_MODEL',''):
            self.assertFalse(vision.status()['available'])

    def test_missing_yolo_file_never_attempts_download(self):
        with patch.object(vision,'YOLO_PATH','not-present.pt'):
            self.assertFalse(vision.status()['available'])
            code,_=vision.detect_yolo('unused',maintenance.PARTS)
        self.assertEqual(code,503)

    def test_yolo_backend_takes_priority_over_language_model(self):
        with patch.object(vision,'YOLO_PATH','local.pt'):
            self.assertEqual(vision.status('local-vision')['backend'],'yolo')

    def test_known_class_boxes_are_normalized_and_filtered(self):
        rows=[[-.1,.2,1.2,.8,.9,1],[.1,.1,.4,.4,.3,1],[.1,.1,.4,.4,.8,2],[.4,.4,.1,.1,.9,1]]
        detections=vision.normalize_detections(rows,{1:'battery',2:'person'},maintenance.PARTS)
        self.assertEqual(len(detections),1)
        self.assertEqual(detections[0]['box'],[0,.2,1,.8])
        self.assertEqual(detections[0]['id'],'battery')

    def test_numeric_class_mapping_is_explicit(self):
        rows=[[.1,.2,.4,.7,.8,0]]
        self.assertEqual(vision.normalize_detections(rows,{0:'car-part'},maintenance.PARTS),[])
        self.assertEqual(vision.normalize_detections(rows,{0:'car-part'},maintenance.PARTS,{'0':'air-cleaner'})[0]['id'],'air-cleaner')

    def test_non_finite_boxes_are_rejected(self):
        self.assertEqual(vision.normalize_detections([[float('nan'),0,1,1,.9,0]],{0:'battery'},maintenance.PARTS),[])

    def test_frame_decoder_checks_type_and_dimensions(self):
        stream=io.BytesIO();Image.new('RGB',(20,10)).save(stream,format='JPEG')
        image=vision.decode_image(base64.b64encode(stream.getvalue()).decode())
        self.assertEqual(image.size,(20,10));image.close()
        with self.assertRaises(Exception):vision.decode_image(base64.b64encode(b'not an image').decode())

    def test_busy_inference_is_rejected_without_queue(self):
        vision.LOCK.acquire()
        try:
            code,_=maintenance.identify('unused')
            self.assertEqual(code,429)
        finally:vision.LOCK.release()

    def test_mock_detector_returns_boxes_without_saving_frames(self):
        class Tensor:
            def __init__(self,value):self.value=value
            def cpu(self):return self
            def tolist(self):return self.value
        class Boxes:
            xyxyn=Tensor([[.1,.2,.5,.6]]);conf=Tensor([.91]);cls=Tensor([0])
        class Result:
            boxes=Boxes();names={0:'battery'}
        class Model:
            def predict(self,**kwargs):
                self.kwargs=kwargs
                return [Result()]
        model=Model()
        with patch.object(vision,'status',return_value={'available':True}),patch.object(vision,'MODEL',model),patch.object(vision,'CLASS_MAP_PATH',''),patch.object(vision,'decode_image',return_value=Image.new('RGB',(20,20))):
            code,result=vision.detect_yolo('frame',maintenance.PARTS)
        self.assertEqual(code,200);self.assertEqual(result['detections'][0]['id'],'battery')
        self.assertFalse(model.kwargs['save']);self.assertTrue(result['needsConfirmation'])

if __name__=='__main__':unittest.main()
