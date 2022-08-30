from PIL import Image, ImageFont, ImageDraw
import math
from PIL.ExifTags import TAGS
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import imghdr
import argparse


class ProcessImage:
    def __init__(self, path):
        self.path = Path(path)
        self.open()
    
    
    def open(self):
        self.image = Image.open(self.path)
    

    def get_exifdata(self):
        self.exifdata = {TAGS.get(k, k): v for k, v in self.image.getexif().items()}
        self.date = datetime.strptime(self.exifdata['DateTime'], '%Y:%m:%d %H:%M:%S').date()
    

    def resize(self):
        self.image.thumbnail((800, 800), Image.Resampling.LANCZOS)
    

    def add_watermark(self):
        # sample dimensions
        width, height = self.image.size

        #text_to_be_rotated = 'Harry Moreno'
        text_to_be_rotated = '(C) MIVS'
        message_length = len(text_to_be_rotated)

        # load font (tweak ratio based on your particular font)
        FONT_RATIO = 2
        DIAGONAL_PERCENTAGE = 0.6
        diagonal_length = int(math.sqrt((width**2) + (height**2)))
        diagonal_to_use = diagonal_length * DIAGONAL_PERCENTAGE
        font_size = int(diagonal_to_use / (message_length / FONT_RATIO))
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', font_size)

        # watermark
        opacity = int(256 * 0.2)
        mark_width, mark_height = font.getsize(text_to_be_rotated)
        watermark = Image.new('RGBA', (mark_width, mark_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)
        draw.text((0, 0), text=text_to_be_rotated, font=font, fill=(0, 0, 0, opacity))
        angle = math.degrees(math.atan(height/width))
        watermark = watermark.rotate(angle, expand=1)

        # merge
        wx, wy = watermark.size
        px = int((width - wx)/2)
        py = int((height - wy)/2)
        self.image.paste(watermark, (px, py, px + wx, py + wy), watermark)
    

    def save(self, output_path):
        self.image.save(output_path)


    def close(self):
        self.image.close()


class ProcessDirectory:
    def __init__(self, indir=None, outdir=None, parse=False):
        if parse:
            self.parse_args()
            self.indir = Path(self.args.indir).absolute()
            self.outdir = Path(self.args.outdir).absolute()
            self.min_date = self.args.min_date
        else:
            if indir is None:
                raise Exception('If parse is False must provide indir')
            else:
                self.indir = Path(indir).absolute()
            if outdir is None:
                raise Exception('If parse is False must provide outdir')
            else:
                self.outdir = Path(outdir).absolute()
    

    def parse_args(self):
        parser = argparse.ArgumentParser(description='This program will process all images in a directory to produce reduce sized, watermarked, grouped by date images')
        parser.add_argument('--indir', required=True, help='Directory with input images (can be in subdirectories')
        parser.add_argument('--outdir', required=True, help='Output directory to save files')
        parser.add_argument('--min-date', default='08/07/22', help='Date to begin processing images from, format DD/MM/YY', type=lambda x: datetime.strptime(x, '%d/%m/%y').date())
        self.args = parser.parse_args()


    def get_all_image_paths(self):
        for dirpath, dirnames, filenames in os.walk(self.indir):
            for f in filenames:
                full_f = os.path.join(dirpath, f)
                if imghdr.what(full_f):
                    yield Path(full_f)
    

    def process_images(self):
        os.makedirs(self.outdir, exist_ok=True)
        for f in self.get_all_image_paths():
            image = ProcessImage(f)
            image.get_exifdata()
            if image.date < self.min_date:
                continue
            image.resize()
            image.add_watermark()
            os.makedirs(self.outdir / str(image.date), exist_ok=True)
            image.save(self.outdir / str(image.date) / f.name)
            image.close()


if __name__ == '__main__':
    ProcessDirectory(parse=True).process_images()