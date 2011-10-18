#!/usr/bin/python
# -=- encoding: utf-8 -=-
# Author: Alexandre Bourget 
# Copyright (c) 2008: Alexandre Bourget 
# LICENSE: GPLv3

# How to use this script
# ------------------------
# Create a "content" labeled layer and put a text box (no flowRect), with each
# line looking like:
#
#   background, layer1
#   background, layer2
#   background, layer2, layer3
#   +layer4
#   background, layer2 * 0.5, layer3 * 0.5, layer5
#


import lxml.etree
import sys
import os
import subprocess
import re
import warnings
from optparse import OptionParser

from fields import ReplacementField

try:
    import pyPdf
except:
    pyPdf = None

NS = {
    'svg': 'http://www.w3.org/2000/svg',
    'ink': 'http://www.inkscape.org/namespaces/inkscape',
}

def main():
    # HIDE DEPRECATION WARINGS ONLY IN RELEASES. SHOW THEM IN DEV. TRUNKS
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    usage = "Usage: %prog [options] svgfilename"
    parser = OptionParser(usage=usage)
    parser.add_option("-i", "--imageexport", action="store_true", dest="imageexport", default=False, help="Use PNG files as export content")
    parser.add_option("-J", "--nojoin", action="store_true", dest="nojoin", default=False, help="Do not join resulting PDFs or PNGs")
    
    (options, args) = parser.parse_args()
    if not args:
        print parser.print_help()
        sys.exit(1)
    
    options.filename = args[0]
    
    maker = InkscapeSlideMaker(options)
    maker.make().join()

# XML utility functions
def e(ns, tag):
    return '{%s}%s' % (ns, tag)

def set_style(el, style, value):
    """Set the display: style, add it if it isn't there, don't touch the
    rest
    """
    if re.search(r'%s: ?[a-zA-Z0-9.]*' % style, el.attrib['style']):
        el.attrib['style'] = re.sub(r'(.*%s: ?)([a-zA-Z0-9.]*)(.*)' % style,
                                    r'\1%s\3' % value, el.attrib['style'])
    else:
        el.attrib['style'] = '%s:%s;%s' % (style, value, el.attrib['style'])
        
class InkscapeSlideMaker(object):
    def __init__(self, options):
        self.doc = lxml.etree.parse(options.filename)
        self.options = options
        
        # Get all layers
        self.layers = [x for x in self.doc.getroot().iterdescendants(tag=e(NS['svg'],'g')) if x.attrib.get(e(NS['ink'],'groupmode'), False) == 'layer']
        try:
            # Scan the 'content' layer
            self.content = [x for x in self.layers if x.attrib.get(e(NS['ink'],'label'), False).lower() == 'content'][0]
        except:
            print """
No 'content'-labeled layer. Create a 'content'-labeled layer and "\
put a text box (no flowRect), with each line looking like:"

    background, layer1"
    background, layer2"
    background, layer2, layer3"
    background, layer2 * 0.5, layer3"
    +layer4 * 0.5"

each name being the label of another layer. Lines starting with
a '+' will add to the layers of the preceding line, creating
"incremental display (note there must be no whitespace before '+')
        
The opacity of a layer can be set to 50% for example by adding 
'*0.5' after the layer name."""
            sys.exit(1)

        # Find the text stuff, everything starting with SLIDE:
        #   take all the layer names separated by ','..
        self.preslides = [x.text for x in self.content.findall('%s/%s' % (e(NS['svg'],'text'), e(NS['svg'],'tspan'))) if x.text]


        if not self.preslides:
            print """Make sure you have a text box (with no flowRect) in the
                'content' layer, and rerun this program."""
            sys.exit(1)
        
        self.orig_style = {}
        self.slides = []
        self.pdfslides = []
        self.slide_number = 0
        
                                                
        self.joinedpdf = False
        
        self.outputFilename = "%s.pdf" % self.options.filename.split(".svg")[0]
        self.outputDir = os.path.dirname(self.outputFilename)
        self.pngPath = os.path.join(self.outputDir, "_inkscapeslide_*.png")
            
    def make(self):
        # Get the initial style attribute and keep it
        for l in self.layers:
            label = l.attrib.get(e(NS['ink'],'label')) 
            if 'style' not in l.attrib:
                l.set('style', '')
            # Save initial values
            self.orig_style[label] = l.attrib['style']


        # Contains seq of [('layer', opacity), ('layer', opacity), ..]
        for sl in self.preslides:
            if sl:
                if sl.startswith('+'):
                    sl = sl[1:]
                    sl_layers = self.slides[-1].copy()
                else:
                    sl_layers = {}

                for layer in sl.split(','):
                    elements = layer.strip().split('*')
                    name = elements[0].strip()
                    opacity = None
                    if len(elements) == 2:
                        opacity = float(elements[1].strip())
                    sl_layers[name] = {'opacity': opacity}
                self.slides.append(sl_layers)


        for i, slide_layers in enumerate(self.slides):
            # Increase slide numbers 
            self.slide_number += 1
            for l in self.layers:
                for text in l.findall('%s/%s' % (e(NS['svg'],'text'), e(NS['svg'],'tspan'))):
                    for field in reversed(ReplacementField.__subclasses__()):
                        field.restore(text)
            
            for l in self.layers:
                label = l.attrib.get(e(NS['ink'],'label'))
                # Set display mode to original
                l.set('style', self.orig_style[label])

                # Don't show it by default...
                set_style(l, 'display', 'none')

                if label in slide_layers:
                    set_style(l, 'display', 'inline')
                    opacity = slide_layers[label]['opacity']
                    if opacity:
                        set_style(l, 'opacity', str(opacity))
                        
                # Update field values
                texts = l.findall('%s/%s' % (e(NS['svg'],'text'), e(NS['svg'],'tspan')))
                for field in ReplacementField.__subclasses__():
                    field_texts = [x for x in texts if field.match(x.text)]
                    
                    for field_text in field_texts:
                        field.replace(field_text, self)
                    
            
            svgslide = os.path.abspath(os.path.join(os.curdir,
                                                    "%s.p%d.svg" % (self.options.filename, i)))
            pdfslide = os.path.abspath(os.path.join(os.curdir,
                                                    "%s.p%d.pdf" % (self.options.filename, i)))
            # Use the correct extension if using images
            if self.options.imageexport:
                pdfslide = os.path.abspath(os.path.join(os.curdir,
                                                "_inkscapeslide_%s.p%05d.png" % (self.options.filename, i)))

            # Write the XML to file, "wireframes.p1.svg"
            self.doc.write(svgslide)

            # Determine whether to export pdf's or images (e.g. inkscape -A versus inkscape -e)
            if self.options.imageexport:
                cmd = "inkscape -d 180 -e %s %s" % (pdfslide, svgslide)
            else:
                cmd = "inkscape -A %s %s" % (pdfslide, svgslide)

            # Using subprocess to hide stdout
            subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()
            os.unlink(svgslide)
            self.pdfslides.append(pdfslide)

            print "Generated page %d." % (i+1)
        return self

    def join(self):
        if self.options.imageexport and not self.options.nojoin:
            # Use ImageMagick to combine the PNG files into a PDF
            if not os.system('which convert > /dev/null') or not os.system('convert -version'):
                print "Using 'convert' to convert PNG's"
                proc = subprocess.Popen('convert "%s" -resample 180 "%s"' % (self.pngPath, self.outputFilename),
                                        shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                # See if the command succeeded
                stdout_value, stderr_value = proc.communicate()
                if proc.returncode:
                    print "\nERROR: convert command failed:"
                    print stderr_value
                else:
                    self.joinedpdf = True
            else:
                print "Please install ImageMagick to provide the 'convert' utility"
        elif not self.options.nojoin:

            if pyPdf:
                print "Using 'pyPdf' to join PDFs"
                output = pyPdf.PdfFileWriter()
                inputfiles = []
                for slide in self.pdfslides:
                    inputstream = file(slide, "rb")
                    inputfiles.append(inputstream)
                    input = pyPdf.PdfFileReader(inputstream)
                    output.addPage(input.getPage(0))
                outputStream = file(self.outputFilename, "wb")
                output.write(outputStream)
                outputStream.close()
                for f in inputfiles:
                    f.close()
                self.joinedpdf = True

            # Verify pdfjoin exists in PATH
            elif not os.system('which pdfjoin > /dev/null'):
                # In the end, run: pdfjoin wireframes.p*.pdf -o Wireframes.pdf
                print "Using 'pdfsam' to join PDFs"
                os.system("pdfjoin --outfile %s.pdf %s" % (FILENAME.split(".svg")[0],
                                                           " ".join(self.pdfslides)))
                self.joinedpdf = True

            # Verify pdftk exists in PATH
            elif not os.system('which pdftk > /dev/null'):
                # run: pdftk in1.pdf in2.pdf cat output Wireframes.pdf
                print "Using 'pdftk' to join PDFs"
                os.system("pdftk %s cat output %s.pdf" % (" ".join(self.pdfslides),
                                                           FILENAME.split(".svg")[0]))
                self.joinedpdf = True
            else:
                print "Please install pdfjam, pdftk or install the 'pyPdf' python package, to join PDFs."

        # Clean up
        if self.joinedpdf and not self.options.nojoin:
            for pdfslide in self.pdfslides:
                os.unlink(pdfslide)
