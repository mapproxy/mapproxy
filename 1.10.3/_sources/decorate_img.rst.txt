Decorate Image
==============

MapProxy provides the ability to update the image produced in response to a WMS GetMap or Tile request prior to it being sent to the client. This can be used to decorate the image in some way such as applying an image watermark or applying an effect.

.. note:: Some Python programming and knowledge of `WSGI <http://wsgi.org>`_ and WSGI middleware is required to take advantage of this feature.

Decorate Image Middleware
-------------------------

The ability to decorate the response image is implemented as WSGI middleware in a similar fashion to how :doc:`authorization <auth>` is handled. You must write a WSGI filter which wraps the MapProxy application in order to register a callback which accepts the ImageSource to be decorated.

The callback is registered by assigning a function to the key ``decorate_img`` in the WSGI environment. Prior to the image being sent in the response MapProxy checks the environment and calls the callback passing the ImageSource and a number of other parameters related to the current request. The callback must then return a valid ImageSource instance which will be sent in the response.

WSGI Filter Middleware
~~~~~~~~~~~~~~~~~~~~~~

A simple middleware that annotates each image with information about the request might look like::

  from mapproxy.image import ImageSource
  from PIL import ImageColor, ImageDraw, ImageFont


  def annotate_img(image, service, layers, environ, query_extent, **kw):
      # Get the PIL image and convert to RGBA to ensure we can use black
      # for the text
      img = image.as_image().convert('RGBA')

      text = ['service: %s' % service]
      text.append('layers: %s' % ', '.join(layers))
      text.append('srs: %s' % query_extent[0])

      text.append('bounds:')
      for coord in query_extent[1]:
          text.append('  %s' % coord)

      draw = ImageDraw.Draw(img)
      font = ImageFont.load_default()
      fill = ImageColor.getrgb('black')

      line_y = 10
      for line in text:
          line_w, line_h = font.getsize(line)
          draw.text((10, line_y), line, font=font, fill=fill)
          line_y = line_y + line_h

      # Return a new ImageSource specifying the updated PIL image and
      # the image options from the original ImageSource
      return ImageSource(img, image.image_opts)

  class RequestInfoFilter(object):
      """
      Simple MapProxy decorate_img middleware.

      Annotates map images with information about the request.
      """
      def __init__(self, app, global_conf):
          self.app = app

      def __call__(self, environ, start_response):
          # Add the callback to the WSGI environment
          environ['mapproxy.decorate_img'] = annotate_img

          return self.app(environ, start_response)

You need to wrap the MapProxy application with your custom decorate_img middleware. For deployment scripts it might look like::

    application = make_wsgi_app('./mapproxy.yaml')
    application = RequestInfoFilter(application)

For `PasteDeploy`_ you can use the ``filter-with`` option. The ``config.ini`` looks like::

  [app:mapproxy]
  use = egg:MapProxy#app
  mapproxy_conf = %(here)s/mapproxy.yaml
  filter-with = requestinfo

  [filter:requestinfo]
  paste.filter_app_factory = mydecoratemodule:RequestInfoFilter

  [server:main]
  ...

.. _`PasteDeploy`: http://pythonpaste.org/deploy/

MapProxy Decorate Image API
---------------------------

The signature of the decorate_img function:

.. function:: decorate_img(image, service, layers=[], environ=None, query_extent=None, **kw)

  :param image: ImageSource instance to be decorated
  :param service: service associated with the current request (e.g. ``wms.map``, ``tms`` or ``wmts``)
  :param layers: list of layer names specified in the request
  :param environ: the request WSGI environment
  :param query_extent: a tuple of the SRS (e.g. ``EPSG:4326``) and the BBOX
    of the request
  :rtype: ImageSource

  The ``environ`` and ``query_extent`` parameters are optional and can be ignored by the callback. The arguments might get extended in future versions of MapProxy. Therefore you should collect further arguments in a catch-all keyword argument (i.e. ``**kw``).

.. note:: The actual name of the callable is insignificant, only the environment key ``mapproxy.decorate_img`` is important.

The function should return a valid ImageSource instance, either the one passed or a new instance depending the implementation.

