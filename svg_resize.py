#!/usr/bin/python

# Resize SVG and add frame for printing in a given format.
# Written by Ilya Zverev, licensed WTFPL.

import sys, os, argparse, re
from lxml import etree

# is there a good way to get rid of this function?
def prepare_options(options):
	if 'width' not in options:
		options['width'] = None
	if 'height' not in options:
		options['height'] = None
	if 'longest' not in options:
		options['longest'] = None
	if 'shortest' not in options:
		options['shortest'] = None
	if 'margin' not in options:
		options['margin'] = '0'
	if not 'trim' in options:
		options['trim'] = False
	if not 'frame' in options:
		options['frame'] = False

def parse_length(value, def_units='px'):
	"""Parses value as SVG length and returns it in pixels, or a negative scale (-1 = 100%)."""
	if not value:
		return 0.0
	parts = re.match(r'^\s*(-?\d+(?:\.\d+)?)\s*(px|in|cm|mm|pt|pc|%)?', value)
	if not parts:
		raise Exception('Unknown length format: "{}"'.format(value))
	num = float(parts.group(1))
	units = parts.group(2) or def_units
	if units == 'px':
		return num
	elif units == 'pt':
		return num * 1.25
	elif units == 'pc':
		return num * 15.0
	elif units == 'in':
		return num * 90.0
	elif units == 'mm':
		return num * 3.543307
	elif units == 'cm':
		return num * 35.43307
	elif units == '%':
		return -num / 100.0
	else:
		raise Exception('Unknown length units: {}'.format(units))

def resize_svg(tree, options):
	prepare_options(options)
	svg = tree.getroot()
	if 'width' not in svg.keys() or 'height' not in svg.keys():
		raise Exception('SVG header must contain width and height attributes')
	width = parse_length(svg.get('width'))
	height = parse_length(svg.get('height'))
	viewbox = re.split('[ ,\t]+', svg.get('viewBox', '').strip())
	if len(viewbox) == 4:
		for i in [0, 1, 2, 3]:
			viewbox[i] = parse_length(viewbox[i])
		if viewbox[2] * viewbox[3] <= 0.0:
			viewbox = None
	else:
		viewbox = None
	if width <= 0 or height <= 0:
		if viewbox:
			width = viewbox[2]
			height = viewbox[3]
		else:
			raise Exception('SVG width and height should be in absolute units and non-zero')
	if not viewbox:
		viewbox = [0, 0, width, height]

	# read and convert size and margin values
	margin = parse_length(options['margin'], 'mm')
	twidth = None
	theight = None
	if options['width']:
		twidth = parse_length(options['width'], 'mm')
	if options['height']:
		theight = parse_length(options['height'], 'mm')
	if options['longest']:
		value = parse_length(options['longest'], 'mm')
		if width > height:
			twidth = value
		else:
			theight = value
	if options['shortest']:
		value = parse_length(options['shortest'], 'mm')
		if width < height:
			twidth = value
		else:
			theight = value

	# twidth and theight are image dimensions without margins
	if twidth:
		if twidth < 0:
			twidth = -width * twidth
		elif twidth > 0:
			twidth = max(0, twidth - margin * 2)
	if theight:
		if theight < 0:
			theight = -height * theight
		elif theight > 0:
			theight = max(0, theight - margin * 2)

	if not twidth:
		if not theight:
			twidth = width
			theight = height
		else:
			twidth = theight / height * width
	if not theight:
		theight = twidth / width * height

	# set svg width and height, update viewport for margin
	svg.set('width', '{}px'.format(twidth + margin * 2))
	svg.set('height', '{}px'.format(theight + margin * 2))
	offsetx = 0
	offsety = 0
	if twidth / theight > viewbox[2] / viewbox[3]:
		# target page is wider than source image
		page_width = viewbox[3] / theight * twidth
		offsetx = (page_width - viewbox[2]) / 2
		page_height = viewbox[3]
	else:
		page_width = viewbox[2]
		page_height = viewbox[2] / twidth * theight
		offsety = (page_height - viewbox[3]) / 2
	vb_margin = page_width / twidth * margin
	svg.set('viewBox', '{} {} {} {}'.format(viewbox[0] - vb_margin - offsetx, viewbox[1] - vb_margin - offsety, page_width + vb_margin * 2, page_height + vb_margin * 2))

	# add frame
	if options['frame']:
		nsm = {'inkscape': 'http://www.inkscape.org/namespaces/inkscape', 'sodipodi': 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd'}
		layer = etree.SubElement(svg, 'g', nsmap=nsm)
		layer.set('{{{}}}groupmode'.format(nsm['inkscape']), 'layer')
		layer.set('{{{}}}label'.format(nsm['inkscape']), 'Frame')
		layer.set('{{{}}}insensitive'.format(nsm['sodipodi']), 'true')
		frame = etree.SubElement(layer, 'path')
		frame.set('style', 'fill:#ffffff;stroke:none')
		bleed = min(page_width, page_height) / 100
		frame.set('d', 'M {0} {1} v {3} h {2} v -{3} z M {4} {5} h {6} v {7} h -{6} z'.format(-viewbox[0] - vb_margin - offsetx - bleed, -viewbox[1] - vb_margin - offsety - bleed, page_width + (vb_margin + bleed) * 2, page_height + (vb_margin + bleed) * 2, viewbox[0], viewbox[1], viewbox[2], viewbox[3]))

def process_stream(options):
	if 'input' not in options or options['input'] is None or options['input'] == '':
		options['input'] = '-'
	if 'output' not in options or options['output'] is None or options['output'] == '':
		options['output'] = options['input']

	tree = etree.parse(sys.stdin if options['input'] == '-' else options['input'])
	resize_svg(tree, options);
	tree.write(sys.stdout if options['output'] == '-' else options['output'])

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Resize SVG and add a frame for printing.')
	parser.add_argument('input', help='source svg file ("-" for stdin, which is default)', nargs='?', default='-')
	parser.add_argument('output', help='destination svg file ("-" for stdout, skip for the same as source)', nargs='?')
	parser.add_argument('-x', '--width', help='target width (including margins, default units are mm)')
	parser.add_argument('-y', '--height', help='target height (including margins, default units as mm)') # choose smaller of two
	parser.add_argument('-l', '--longest', help='target longest side')
	parser.add_argument('-s', '--shortest', help='target shortest side')
	parser.add_argument('-m', '--margin', help='margin (default units are mm)', default='0')
	parser.add_argument('-f', '--frame', action='store_true', help='add white frame around the picture')
	options = parser.parse_args()
	process_stream(vars(options))
