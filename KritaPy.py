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

def parse_svg(src, gscripts, x=0, y=0, kra_fname=''):
	svg = xml.dom.minidom.parseString(open(src).read())
	print(svg.toxml())
	for g in svg.getElementsByTagName('g'):
		for c in g.childNodes:
			if hasattr(c, 'tagName') and c.tagName=='desc':
				gscripts[g.getAttribute('id')] = c.firstChild.nodeValue
				break

	bobs = []
	texts = svg.getElementsByTagName('text')
	if texts:
		for t in texts:
			if not len(t.childNodes): continue
			print(t.toxml())
			tid = t.getAttribute('id')
			tx  = float(t.getAttribute('x'))
			ty  = float(t.getAttribute('y'))
			tscl = t.getAttribute('transform')
			if tscl.startswith('scale('):
				tsx, tsy = tscl.split('(')[-1].split(')')[0].split(',')
				tsx = float(tsx)
				tsy = float(tsy)
			inkscript = []
			for child in t.childNodes:
				if child.tagName=='desc':
					## INKSCAPE metadata
					inkscript.append(child.firstChild.nodeValue)
				elif child.tagName=='tspan':
					style = child.getAttribute('style')
					fontsize = style.split('font-size:')[-1].split(';')[0]
					assert fontsize.endswith('px')
					fontsize = float(fontsize[:-2])
					text = child.firstChild.nodeValue
					if bpy:
						bpy.ops.object.text_add()
						ob = bpy.context.active_object
						ob.data.body = text
						ob.name = tid
						ob.rotation_euler.x = math.pi/2
						ob.data.size=fontsize * 0.01 * 2
						ob.scale.x = tsx
						ob.scale.y = tsy
						bobs.append(ob)
						if inkscript:
							sco = {'bpy':bpy, 'self':ob, 'math':math, 'random':random}
							sco[tid] = ob
							txt = bpy.data.texts.new(name=tid+'.'+kra_fname)
							txt.from_string('\n'.join(inkscript))
							SCRIPTS.append({'scope':sco, 'script':txt})
	if bpy:
		#bpy.ops.wm.gpencil_import_svg(filepath=src, scale=100, resolution=5)
		#ob = bpy.context.active_object
		#ob.name = layer.getAttribute('name')
		#bobs.append(ob)
		#ob.location.x = x * 0.01
		#ob.location.z = -y * 0.01 
		for g in svg.getElementsByTagName('g'):
			is_leaf = True
			for c in g.childNodes:
				if hasattr(c,'tagName') and c.tagName=='g':
					is_leaf=False
					break
			if not is_leaf:
				continue
			gsvg = [
				'<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
				'<svg width="%s" height="%s" viewBox="%s" version="1.1">' % (
					svg.documentElement.getAttribute('width'),
					svg.documentElement.getAttribute('height'),
					svg.documentElement.getAttribute('viewBox'),
				),
				svg.getElementsByTagName('defs')[0].toxml(),
				g.toxml(),
				'</svg>',
			]
			open('/tmp/%s.svg', 'w').write('\n'.join(gsvg))
			#bpy.ops.wm.gpencil_import_svg(filepath=src, scale=100, resolution=5)
			bpy.ops.wm.gpencil_import_svg(filepath=src, scale=50, resolution=5)
			ob = bpy.context.active_object
			#ob.name = layer.getAttribute('name')
			ob.name = g.getAttribute('id')
			bobs.append(ob)
			ob.location.x = x * 0.01
			ob.location.z = -y * 0.01
			if ob.name in gscripts:
				sco = {'bpy':bpy, 'self':ob, 'math':math, 'random':random}
				sco[ob.name] = ob
				txt = bpy.data.texts.new(name=ob.name+'.'+kra_fname)
				txt.from_string(gscripts[ob.name])
				SCRIPTS.append({'scope':sco, 'script':txt})

	return bobs

def parse_kra(kra, verbose=False, blender_curves=False):
	kra_fname = os.path.split(kra)[-1]
	arc = zipfile.ZipFile(kra,'r')
	print(arc)
	dump = {'layers':[]}
	groups = {}
	layers = {}
	bobs = []

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
	obscripts = {}
	gscripts  = {}
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
			if src.endswith('.svg'):
				bobs += parse_svg( src, gscripts, x=x, y=y, kra_fname=kra_fname )

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
				elif src.endswith(('.png', '.jpg', '.webp', '.tga', '.tif', '.bmp')):
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
	svgs = []
	output = None
	do_strip = False
	for arg in sys.argv:
		if arg.startswith('--output='):
			output = arg.split('=')[-1]
		elif arg.endswith('.kra'):
			kras.append(arg)
		elif arg.endswith('.svg'):
			svgs.append(arg)
		elif arg=='--blender':
			run_blender=True
		elif arg=='--strip':
			do_strip = True

	if do_strip:
		if not output:
			print('error: output=FILE is required with --strip')
			raise RuntimeError('invalid command line args with option --strip: %s' % sys.argv)
		elif not kras:
			print('error: input .kra file required with --strip')
			raise RuntimeError('invalid command line args with option --strip: %s' % sys.argv)

		kra = kras[0]
		assert output != kra

		krain = zipfile.ZipFile(kra,'r')
		kraout = zipfile.ZipFile(output, 'w')
		for f in krain.filelist:
			if f.filename=='mergedimage.png':
				print('skipping', f)
				continue
			print('saving:', f)
			kraout.writestr(f, krain.read(f.filename))
		print('saving stripped:', output)
		kraout.close()
		sys.exit()
	elif svgs:
		for s in svgs:
			parse_svg(s, {})
	elif run_blender:
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
