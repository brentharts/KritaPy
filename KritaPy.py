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
	kra_fname = os.path.split(kra)[-1]
	arc = zipfile.ZipFile(kra,'r')
	print(arc)
	dump = {'layers':[]}
	groups = {}
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
		#sub = IMAGE.getAttribute('description')  ## always empty?
		pyscript = info.getElementsByTagName('abstract')[0]
		pyscript = pyscript.firstChild.nodeValue
	else:
		pyscript = None

	bprops = info.getElementsByTagName('keyword')
	if bprops and bprops[0].firstChild:
		bprops = bprops[0].firstChild.nodeValue.split()
	else:
		bprops = None

	pixlayers = []
	reflayers = []
	xlayers = {}
	for layer in doc.getElementsByTagName('layer'):
		print(layer.toxml())
		ob = parent = None
		x = int(layer.getAttribute('x'))
		y = int(layer.getAttribute('y'))
		tag = layer.getAttribute('filename')
		xlayers[tag] = layer

		## check if parent layer is a group
		if layer.parentNode and layer.parentNode.tagName == 'layers':
			if layer.parentNode.parentNode.tagName=='IMAGE':
				print('root layer:', layer)
			elif layer.parentNode.parentNode.tagName=='layer':
				g = layer.parentNode.parentNode
				print('layer parent:', g)
				parent = groups[g.getAttribute('name')]['root']

		if layer.getAttribute('nodetype')=='grouplayer':
			if bpy:
				bpy.ops.object.empty_add(type="CIRCLE")
				ob = bpy.context.active_object
				ob.name = layer.getAttribute('name')
				bobs.append(ob)
				ob.location.x = (x-(width/2)) * 0.01
				ob.location.z = -(y-(height/2)) * 0.01 

			groups[layer.getAttribute('name')] = {
				'x': int(layer.getAttribute('x')),
				'y': int(layer.getAttribute('y')),
				'children':[],
				'root':ob,
			}

		elif layer.getAttribute('nodetype')=='shapelayer':
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
			if not int(layer.getAttribute('visible')):
				print('skip layer:', tag)
			else:
				pixlayers.append( tag )
		elif layer.getAttribute('nodetype')=='filelayer':
			src = layer.getAttribute('source')
			assert os.path.isfile(src)
			reflayers.append( {'source':src, 'x':x, 'y':y} )
			if bpy:
				if src.endswith('.kra'):
					## nested kra
					bpy.ops.object.empty_add(type="SINGLE_ARROW")
					ob = bpy.context.active_object
					ob.name = src
					bobs.append(ob)
					ob['KRITA'] = src
					if parent:
						ob.location.x = x * 0.01
						ob.location.z = -y * 0.01 
					else:
						ob.location.x = (x-(width/2)) * 0.01
						ob.location.z = -(y-(height/2)) * 0.01 
				else:
					bpy.ops.object.empty_add(type="IMAGE")
					ob = bpy.context.active_object
					bobs.append(ob)
					img = bpy.data.images.load(src)
					ob.data = img
					ob.location.x = (x-(width/2)) * 0.01
					ob.location.z = -(y-(height/2)) * 0.01 
					ob.rotation_euler.x = math.pi/2
					ob.scale.x = img.width * 0.01
					ob.scale.y = img.height * 0.01
		if bpy and parent:
			ob.parent = parent

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
			ob.location.y = len(pixlayers) * 0.001 * height
			ob.name = xlayers[tag].getAttribute('name')
			ob.rotation_euler.x = math.pi/2
			ob.scale.x = width * 0.01
			ob.scale.y = height * 0.01

	if bpy:
		col = bpy.data.collections.new(kra_fname)
		bpy.context.scene.collection.children.link(col)

		bpy.ops.object.empty_add(type="ARROWS")
		root = bpy.context.active_object
		col.objects.link(root)
		for o in bobs:
			if not o.parent:
				o.parent = root
			col.objects.link(o)

		if bprops:
			for p in bprops:
				v = 0.0
				if '=' in p:
					n,v = p.split('=')
					try: v = float(v)
					except: pass
				else:
					n = p
				root[n] = float(v)



	if bpy and pyscript:
		scope = {'bpy':bpy, 'random':random, 'uniform':uniform, 'self':root}
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

	if bpy:
		return col
	else:
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
	elif kras:
		for kra in kras:
			a = parse_kra( kra, verbose='--verbose' in sys.argv )
	elif bpy:
		pass
	else:
		print('no krita .kra files given')


## in blender below this point ##
if not bpy: sys.exit()
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


_lazy_loads = {}
_timer = None
@bpy.utils.register_class
class KritaPyOperator(bpy.types.Operator):
	"Krita Python Scripts"
	bl_idname = "krita.run"
	bl_label = "krita_run"
	bl_options = {'REGISTER'}
	def modal(self, context, event):
		if event.type == "TIMER":
			for o in bpy.data.objects:
				if 'KRITA' in o.keys():
					kra = o['KRITA']
					if not kra: continue
					if kra not in _lazy_loads:
						col = parse_kra(kra)
						_lazy_loads[kra] = col
					o.instance_type = 'COLLECTION'
					o.instance_collection = _lazy_loads[kra]
					o['KRITA']=None

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
