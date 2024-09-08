# KritaPy
Python utilities for working with Krita .kra files. In particular,
reading them, because Krita's command-line performance leaves
something to be desired.

# Blender
Exports from Krita to Blender, works from command line or the Blender interface (World panel)

## Command line

Usage:
`python3 KritaPy.py --blender`

## Python Scripts in .kra

Krita .kra files support metadata: document title and description.
If you put blender bpy python code in the description and your title
ends with `.py`, that code will be run every frame in blender.
Your layer names will become local variables in the scope of code.
