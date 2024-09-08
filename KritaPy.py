#!/usr/bin/env python3
import os, sys, io, zipfile, xml.dom.minidom, subprocess, math
from random import random, uniform

try:
	import bpy
except:
	bpy = None

SCRIPTS = []

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

	x = arc.read('documentinfo.xml')
	if verbose:
		print('-'*80)
		print(x.decode('utf-8'))
		print('-'*80)
	info = xml.dom.minidom.parseString(x)
	print(info)


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
		#pyscript = IMAGE.getAttribute('description')  ## not the right one
		pyscript = info.getElementsByTagName('abstract')[0]
		pyscript = pyscript.firstChild.nodeValue
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
		scope = {'bpy':bpy, 'random':random, 'uniform':uniform}
		gen = []
		for ob in bobs:
			scope[ safename(ob.name) ] = ob
			gen.append('%s = bpy.data.objects["%s"]' % (safename(ob.name), ob.name))
		print('exec script:')
		print(pyscript)
		gen.append(pyscript)
		txt = bpy.data.texts.new(name='__krita2blender__.py')
		#txt.from_string(PYHEADER + '\n'.join(gen))
		#exec(pyscript, scope)
		txt.from_string(pyscript)
		SCRIPTS.append({'scope':scope, 'script':txt})

	else:
		print('user python script:', pyscript)

	return dump

PYHEADER = '''
import bpy, mathutils
from random import random, uniform
'''

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

## in blender below this point ##
from bpy_extras.io_utils import ImportHelper

@bpy.utils.register_class
class Krita4Blender(bpy.types.Operator, ImportHelper):
	bl_idname = 'krita.import_kra'
	bl_label  = 'Import Krita File (.kra)'
	filter_glob : bpy.props.StringProperty(default='*.kra')
	def execute(self, context):
		parse_kra(self.filepath)
		return {'FINISHED'}

@bpy.utils.register_class
class KritaWorldPanel(bpy.types.Panel):
	bl_idname = "WORLD_PT_KritaWorld_Panel"
	bl_label = "Krita"
	bl_space_type = "PROPERTIES"
	bl_region_type = "WINDOW"
	bl_context = "world"
	def draw(self, context):
		self.layout.operator("krita.import_kra")



_timer = None
@bpy.utils.register_class
class KritaPyOperator(bpy.types.Operator):
	"Krita Python Scripts"
	bl_idname = "krita.run"
	bl_label = "krita_run"
	bl_options = {'REGISTER'}
	def modal(self, context, event):
		if event.type == "TIMER":
			for s in SCRIPTS:
				scope  = s['scope']
				script = s['script'].as_string()
				exec(script, scope, scope)
		return {'PASS_THROUGH'} # will not supress event bubbles

	def invoke (self, context, event):
		global _timer
		if _timer is None:
			_timer = self._timer = context.window_manager.event_timer_add(
				time_step=0.025,
				window=context.window
			)
			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}
		return {'FINISHED'}

	def execute (self, context):
		return self.invoke(context, None)
bpy.ops.krita.run()
