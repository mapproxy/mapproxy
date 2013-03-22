from mapproxy.image import ImageSource
from mapproxy.platform.image import Image
from mapproxy.service.base import Server
from mapproxy.test.http import make_wsgi_env
from nose.tools import raises, eq_

class TestPostProcess(object):

    def test_original_imagesource_returned_when_no_callback(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={})
        img_src2 = Server.postprocess_image(img_src1, env)
        eq_(img_src1, img_src2)

    def test_returns_imagesource(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={})
        img_src2 = Server.postprocess_image(img_src1, env)
        assert isinstance(img_src2, ImageSource)

    def set_called_callback(self, img_src):
        self.called = True
        return img_src

    def test_calls_callback(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        self.called = False
        env = make_wsgi_env('', extra_environ={'mapproxy.postprocess': self.set_called_callback})
        img_src2 = Server.postprocess_image(img_src1, env)
        eq_(self.called, True)

    def return_new_imagesource_callback(self, img_src):
        new_img_src = ImageSource(Image.new('RGBA', (100, 100)))
        self.new_img_src = new_img_src
        return new_img_src

    def test_returns_callbacks_return_value(self):
        img_src1 = ImageSource(Image.new('RGBA', (100, 100)))
        env = make_wsgi_env('', extra_environ={'mapproxy.postprocess': self.return_new_imagesource_callback})
        self.new_img_src = None
        img_src2 = Server.postprocess_image(img_src1, env)
        eq_(img_src2, self.new_img_src)



