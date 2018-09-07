import tempfile
import os.path
import numpy
from PIL import Image
import sys


def gen_bitmap(output):
    imarray = numpy.random.rand(200, 200, 3) * 255
    im = Image.fromarray(imarray.astype('uint8')).convert('RGBA')
    im.save(output)


def main(count, folder):
    for i in range(count):
        tf = tempfile.NamedTemporaryFile()
        gen_bitmap(os.path.join(folder, os.path.basename(tf.name) + ".png"))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print "imagen.py <count: integer> <folder: str>"
        exit(-1)

    count = int(sys.argv[1])
    folder = sys.argv[2]

    main(count, folder)
