from select import select
from PIL import Image, ImageFont, ImageDraw
import math
from PIL.ExifTags import TAGS
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import imghdr
import argparse
import pandas as pd
import shutil
from pathlib import Path


class ProcessImage:
    def __init__(self, path):
        self.path = Path(path)
        self.open()
    
    
    def open(self):
        self.image = Image.open(self.path)
    

    def get_exifdata(self):
        self.exifdata = {TAGS.get(k, k): v for k, v in self.image.getexif().items()}
        try:
            self.date = datetime.strptime(self.exifdata['DateTime'], '%Y:%m:%d %H:%M:%S').date()
        except:
            print(self.path)
    

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


    def filter_paths(self, file_names):
        for path in self.get_all_image_paths():
            if path.stem in file_names:
                yield path.stem, path


def read_file_names(file_names_path):
    with open(file_names_path) as f:
        return [line.strip() for line in f.readlines()]


def process_selection(file_names_path, originals_path, processed_path, selected_path):
    selected_path = Path(selected_path)
    file_names = read_file_names(file_names_path)
    originals = ProcessDirectory(originals_path, selected_path)
    processed = ProcessDirectory(processed_path, selected_path)
    original_df = pd.DataFrame(originals.filter_paths(file_names), columns=['stem', 'original_path']).drop_duplicates(subset=['stem']).set_index('stem')
    processed_df = pd.DataFrame(processed.filter_paths(file_names), columns=['stem', 'processed_path']).set_index('stem')
    combined_df = pd.merge(original_df, processed_df, on='stem')
    combined_df['processed_dir'] = combined_df.processed_path.apply(lambda x: x.parent.stem)
    combined_df['camera_dir'] = combined_df.original_path.apply(lambda x: str(x).split(originals_path + '/')[1].split('/', 1)[0])
    print(combined_df.groupby('camera_dir').size())
    legal_text = f'''Use of my Image. I Ilya Vainberg Slutskin, original owner of the images, hereby grant to Oleg Galeev and his website MyTrip2Ecuador.com permission to use the images taken of me and shared via google drive by or on behalf of the MyTrip2Ecuador.com during for commercial or non-commercial materials on the website, in-article use only. I understand that I will not receive any additional compensation for such use (except for the payment $5 per attached photo) and hereby release the MyTrip2Ecuador.com and anyone working on behalf of the website in connection with the use of my images. Oleg Galeev or and anyone working on behalf of the website may not resell the photos or use them anywhere else besides MyTrip2Ecuador.com website. The image file names are:
    {', '.join(combined_df.original_path.apply(lambda x: Path(x).name))}
    '''
    print(legal_text)
    os.makedirs(selected_path, exist_ok=True)
    for row in combined_df.itertuples():
        row_dir = selected_path / row.processed_dir
        os.makedirs(row_dir, exist_ok=True)
        shutil.copy2(row.original_path, row_dir / row.original_path.name)
    return combined_df


def print_legal(file_names_path):
    file_names = read_file_names(file_names_path)
    base_text = f'''Use of my Image. I Ilya Vainberg Slutskin, original owner of the images, hereby grant to Oleg Galeev and his website MyTrip2Ecuador. com permission to use the images taken of me and shared via google drive by or on behalf of the MyTrip2Ecuador. com during for commercial or non-commercial materials on the website, in-article use only. I understand that I will not receive any additional compensation for such use (except for the payment $5 per attached photo) and hereby release the MyTrip2Ecuador. com and anyone working on behalf of the website in connection with the use of my images. Oleg Galeev or and anyone working on behalf of the website may not resell the photos or use them anywhere else besides MyTrip2Ecuador. com website. The image file names are:
    '''

if __name__ == '__main__':
    ProcessDirectory(parse=True).process_images()