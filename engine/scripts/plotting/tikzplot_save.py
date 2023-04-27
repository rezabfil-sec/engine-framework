#!/usr/bin/env python3
# from turtle import color
import matplotlib
import tikzplotlib
import glob
import os
import sys

font = {'weight' : 'normal',
                    'size'   : 20}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)

defParams = ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0"]

sizeDict = {
    'small' : (275, 125),
    'medium' : (275, 200),
    'large' : (275, 275),
    'wide_small' : (550, 125),
    'wide_medium' : (550, 200),
    'wide_large' : (550, 275)
}

def getSize(sizeParam):
    if type(sizeParam) == tuple:
        if sizeParam[0] == 'custom':
            return str(sizeParam[1][0]), str(sizeParam[1][1])
        else:
            sys.exit("Unknown size descriptor in the size parameter tuple!")
    else:
        if sizeParam not in sizeDict:
            sys.exit("Unknown size descriptor given as the size parameter!")
        else:
            return str(sizeDict[sizeParam][0]), str(sizeDict[sizeParam][1])

testingStringLines = [
    "\\usetikzlibrary{math}\n",
    "\\tikzmath\n",
    "{\n",
    "  function symlog(\\x,\\a){\n",
    "    \\yLarge = ((\\x>\\a) - (\\x<-\\a)) * (ln(max(abs(\\x/\\a),1)) + 1);\n",
    "    \\ySmall = (\\x >= -\\a) * (\\x <= \\a) * \\x / \\a ;\n",
    "    return \\yLarge + \\ySmall ;\n",
    "  };\n",
    "  function symexp(\\y,\\a){\n",
    "    \\xLarge = ((\\y>1) - (\\y<-1)) * \\a * exp(abs(\\y) - 1) ;\n",
    "    \\xSmall = (\\y>=-1) * (\\y<=1) * \\a * \\y ;\n",
    "    return \\xLarge + \\xSmall ;\n",
    "  };\n",
    "}\n"
]

def addSymlog(file, modLines, modStart):
    with open(file, "r") as f:
        contents = f.readlines()

    for idx, line in enumerate(modLines):
        contents.insert(modStart+idx, line)

    with open(file, "w") as f:
        contents = "".join(contents)
        f.write(contents)
# name = name of the plot
# path = where to save the plot
# params = parameters for tikz that help with plot saving as list
# Default params if empty list passed:
#   defParams = ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0"]
# size = the pre-defined size of the figure options below available (W x H): Size given as either <descriptor> from list below or tuple ('custom',(W x H)) -> define W x H only if custom descriptor chosen
    # small = 275 x 125
    # medium = 275 x 200
    # large = 275 x 275
    # wide_small = 550 x 125
    # wide_medium = 550 x 200
    # wide_large = 550 x 275
    # custom = select size on your own
def saveTikz(name, path, params, sizeParam, cleanFlag, addSymetricLogYaxis):
    partPath = path + '/' + name
    if cleanFlag:
        print('Tikz clean figure', end='...', flush=True)
        tikzplotlib.clean_figure()
        print('\tDone!', flush=True)
    sizeX, sizeY = getSize(sizeParam)
    print('Exporting to TEX with figure size ' + sizeX + ' x ' + sizeY + ' (W x H) and', end=' ', flush=True)
    if params == []:
        params = defParams
        print('default axis parameters', end='...', flush=True)
    else:
        print('cusom user axis parameters', end='...', flush=True)
    tikzplotlib.save(partPath + '.tex', standalone=True, textsize=30, dpi=300, axis_width=sizeX, axis_height=sizeY, encoding='utf-8', extra_axis_parameters=params)
    print('\tDone!', flush=True)

    if addSymetricLogYaxis == True:
        addSymlog(partPath + '.tex', testingStringLines, 6)
        addSymlog(partPath + '.tex', [
            "\\def\\basis{1}",
            "  \\pgfplotsset",
            "  {",
            "    y coord trafo/.code={\\pgfmathparse{symlog(#1,\\basis)}\\pgfmathresult},",
            "    y coord inv trafo/.code={\\pgfmathparse{symexp(#1,\\basis)}\\pgfmathresult},",
            "    yticklabel style={/pgf/number format/.cd,int detect,precision=2},",
            "  }"
        ], 25)

    os.chdir(path)
    print('Creating PDF based on the exported TEX file', end='...', flush=True)
    os.system('pdflatex -synctex=1 -interaction=nonstopmode --shell-escape --extra-mem-bot=999999999999999999 ' + partPath + '.tex > ' + partPath + '_pdflatex.log 2>&1')
    print('\tDone!', flush=True)
    print('Exporting EPS based on the just created PDF file', end='...', flush=True)
    os.system('pdftops -eps ' + partPath + '.pdf '+ partPath + '.eps > ' + partPath + '_pdftops.log 2>&1')
    print('\tDone!', flush=True)

    print('Cleanup of remaining files', end='...', flush=True)
    # Cleanup after pdflatex
    for f in glob.glob('*.aux'):
        os.remove(f)
    for f in glob.glob('*.gz'):
        os.remove(f)
    print('\tDone!', flush=True)
    print('NOTE: No checks whether this was actually successful were done. Check logs if something does not seem right...')
    print('If all went to plan, the resutls can be found in:', os.path.abspath(os.getcwd()))
    os.getcwd()