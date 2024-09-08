#!/usr/bin/env python3
import os, sys, io, zipfile, xml.dom.minidom, subprocess, math
try:
	import bpy
except:
	bpy = None

def extractMergedImageFromKRA(kra):
	from PIL import Image
	archive = zipfile.ZipFile(kra,'r')
	extract_image = archive.read('mergedimage.png')
	image = Image.open(io.BytesIO(extract_image))
	return image

def parse_kra(kra, verbose=False, blender_curves=False):
	arc = zipfile.ZipFile(kra,'r')
	print(arc)
	dump = {'layers':[]}
	layers = {}
	if bpy: bobs = []

	for f in arc.filelist:
		if verbose: print(f)
		#files.append(f.filename)
		if '/layers/' in f.filename:
			a = f.filename.split('/layers/')[-1]
			print(a)
			tag = a.split('.')[0]
			if tag not in layers:
				layers[tag] = []
			layers[tag].append(f.filename)

	if verbose: print(layers)

	x = arc.read('maindoc.xml')
	if verbose:
		print('-'*80)
		print(x.decode('utf-8'))
		print('-'*80)
	doc = xml.dom.minidom.parseString(x)
	print(doc)

	IMAGE = doc.getElementsByTagName('IMAGE')[0]
	width = int(IMAGE.getAttribute('width'))
	height = int(IMAGE.getAttribute('height'))
	title = IMAGE.getAttribute('name')

	## allows for python logic to be put in a krita description,
	## only if the user renames the title of the document so that
	## it ends with .py, then it will be run in blender python.
	if title.endswith('.py'):
		pyscript = IMAGE.getAttribute('description')
	else:
		pyscript = None

	pixlayers = []
	xlayers = {}
	for layer in doc.getElementsByTagName('layer'):
		print(layer)
		print(layer.toxml())
		tag = layer.getAttribute('filename')
		xlayers[tag] = layer
		if layer.getAttribute('nodetype')=='shapelayer':
			svg = arc.read( layers[tag][0] ).decode('utf-8')
			print(svg)
			dump['layers'].append(svg)
			if bpy:
				svgtmp = '/tmp/__krita2blender__.svg'
				open(svgtmp,'w').write(svg)
				if blender_curves:
					bpy.ops.import_curve.svg(filepath=svgtmp)
					ob = bpy.context.active_object  ## TODO this is not correct?
					ob.name = layer.getAttribute('name') + '.CURVE'
					ob.scale *= 100
					bobs.append(ob)
				bpy.ops.wm.gpencil_import_svg(filepath=svgtmp, scale=100, resolution=5)
				ob = bpy.context.active_object
				ob.name = layer.getAttribute('name')
				bobs.append(ob)
		elif layer.getAttribute('nodetype')=='paintlayer':
			pixlayers.append( tag )


	x = arc.read('documentinfo.xml')
	if verbose:
		print('-'*80)
		print(x)
		print('-'*80)
	#info = xml.dom.minidom.parseString(x)
	#print(info)

	while pixlayers:
		tag = pixlayers.pop()
		print('saving pixel layer:', tag)
		tmp = '/tmp/tmp.kra'
		aout = zipfile.ZipFile(tmp,'w')

		root = doc.getElementsByTagName('layers')[0]
		while root.firstChild: root.removeChild(root.firstChild)
		root.appendChild( xlayers[tag] )

		aout.writestr('maindoc.xml', doc.toxml())
		for f in layers[tag]:
			print(f)
			aout.writestr(
				f, arc.read(f)
			)

		print(aout.filelist)
		aout.close()

		cmd = ['krita', '--export', '--export-filename', '/tmp/%s.png' % tag, tmp]
		print(cmd)
		subprocess.check_call(cmd)

		if bpy:
			print(xlayers[tag].toxml())
			bpy.ops.object.empty_add(type="IMAGE")
			ob = bpy.context.active_object
			bobs.append(ob)
			img = bpy.data.images.load('/tmp/%s.png' % tag)
			ob.data = img
			ob.location.y = len(pixlayers) * 0.1
			ob.name = xlayers[tag].getAttribute('name')
			ob.rotation_euler.x = math.pi/2

	if bpy and pyscript:
		scope = {'bpy':bpy}
		for ob in bobs:
			scope[ safename(ob.name) ] = ob
		exec(pyscript, scope)

	return dump

def safename(n):
	import string
	nope = string.punctuation + string.whitespace
	for c in nope:
		n = n.replace(c,'_')
	return n

if __name__ == "__main__":
	run_blender = False
	kras = []
	for arg in sys.argv:
		if arg.endswith('.kra'):
			kras.append(arg)
		elif arg=='--blender':
			run_blender=True

	if run_blender:
		cmd = ['blender', '--python', __file__]
		if kras: cmd += ['--'] + kras
		print(cmd)
		subprocess.check_call(cmd)
		sys.exit()
	elif kras:
		for kra in kras:
			a = parse_kra( kra, verbose='--verbose' in sys.argv )
	elif bpy:
		pass
	else:
		print('no krita .kra files given')
		sys.exit()

