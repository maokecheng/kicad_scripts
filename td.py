#!/usr/bin/env python

# Teardrop for pcbnew using filled zones
# (c) Niluje 2016 thewireddoesntexist.org
#
# Based on Teardrops for PCBNEW by svofski, 2014 http://sensi.org/~svo

import os, sys
import argparse
import fileinput
from math import cos, sin, asin, radians
from pcbnew import *

__version__ = "0.2.0"

ToUnits=ToMM
FromUnits=FromMM

def __File2List(filename):
    try:
        f = open(filename, 'r')
        listfile = [ l.rstrip() for l in f ]
    except IOError:
        return []
    f.close()
    return listfile

def __List2File(thelist, filename):
    f = open(filename, 'w')
    for l in thelist:
        f.write(l+'\n')
    f.close()

def __GetAllVias(board):
    """Just retreive all via from the given board"""
    vias = []
    vias_selected =[]
    for item in board.GetTracks():
        if type(item) == VIA:
            pos = item.GetPosition()
            width = item.GetWidth()
            drill = item.GetDrillValue()
            vias.append((pos, width, drill))
            if item.IsSelected():
                vias_selected.append((pos, width, drill))
    return vias, vias_selected

def __GetAllPads(board, filters=[]):
    """Just retreive all pads from the given board"""
    pads = []
    pads_selected = []
    for i in xrange(board.GetPadCount()):
        pad = board.GetPad(i)
        if pad.GetAttribute() in filters:
            pos = pad.GetPosition()
            drill = pad.GetDrillSize().x + FromUnits(0.2 * 2)
            pads.append((pos, drill ))
            if pad.IsSelected():
                pads_selected.append((pos, drill))
    return pads, pads_selected

def __Zone(viafile, board, points, track):
    """Add a zone to the board"""
    z = ZONE_CONTAINER(board)

    #Add zone properties
    z.SetLayer(track.GetLayer())
    z.SetNetCode(track.GetNetCode())
    z.SetZoneClearance(track.GetClearance())
    z.SetMinThickness(25400) #The minimum
    z.SetPadConnection(2) # 2 -> solid
    z.SetIsFilled(True)

    line=[]
    for p in points:
        z.AppendCorner(p)
        line.append(str(p))

    line.sort()
    z.BuildFilledSolidAreasPolygons(board)

    #Save zone properties
    vialine = track.GetLayerName() + ':' + ''.join(line)
    if not vialine in viafile:
        viafile.append(vialine)
        return z

    return None

def __Compute4Points(track, via, hpercent, vpercent):
    """Del all teardrops referenced by the teardrop file"""
    start = track.GetStart()
    end = track.GetEnd()

    # ensure that start is at the via/pad end
    d = end - via[0]
    if sqrt(d.x * d.x + d.y * d.y) < via[1]:
        start, end = end, start

    # get normalized track vector
    pt = end - start
    norm = sqrt(pt.x * pt.x + pt.y * pt.y)
    vec = [t / norm for t in pt]

    d = asin(vpercent/100.0);
    vecB = [vec[0]*cos(d)+vec[1]*sin(d) , -vec[0]*sin(d)+vec[1]*cos(d)]
    d = asin(-vpercent/100.0);
    vecC = [vec[0]*cos(d)+vec[1]*sin(d) , -vec[0]*sin(d)+vec[1]*cos(d)]

    # find point on the track, sharp end of the teardrop
    dist = via[1]*(1+hpercent/100.0)
    pointA = start + wxPoint(int(vec[0] * dist), int(vec[1] * dist))

    # Introduce a last point in order to cover the via centre.
    # If not, the zone won't be filled
    vecD = [-vec[0], -vec[1]]

    radius = via[1] / 2

    # via side points
    pointB = via[0] + wxPoint(int(vecB[0] * radius), int(vecB[1] * radius))
    pointC = via[0] + wxPoint(int(vecC[0] * radius), int(vecC[1] * radius))

    # behind via center
    radius = (via[1]/2)*0.5 #50% of via radius is enough to include
    pointD = via[0] + wxPoint(int(vecD[0] * radius), int(vecD[1] * radius))

    return (pointA, pointB, pointD, pointC)

def SetTeardrops(hpercent=30, vpercent=70):
    """Set teardrops on a teardrop free board"""

    pcb = GetBoard()
    td_filename = pcb.GetFileName() + '_td'

    vias = __GetAllVias(pcb)[0] + __GetAllPads(pcb, [PAD_STANDARD])[0]
    vias_selected = __GetAllVias(pcb)[1] + __GetAllPads(pcb, [PAD_STANDARD])[1]
    viasfile = __File2List(td_filename)
    if len(vias_selected) > 0:
        print('Using selected pads/vias')
        vias = vias_selected
    else:
        # If a teardrop file is present AND no pad are selected,
        # remove all teardrops.
        if len(viasfile) > 0:
            RmTeardrops()

    count = 0
    for track in pcb.GetTracks():
        if type(track) == TRACK:
            for via in vias:
                if track.IsPointOnEnds(via[0], via[1]/2):
                    if track.GetLength() < via[1]:
                            continue
                    coor = __Compute4Points(track, via, hpercent, vpercent)
                    the_zone = __Zone(viasfile, pcb, coor, track)
                    if the_zone:
                        pcb.Add(the_zone)
                        count = count + 1

    if len(viasfile) > 0:
        __List2File(viasfile, td_filename)
    else:
        #Just remove the file
        try:
            os.remove(td_filename)
        except IOError:
            #There was no file at startup and no teardrop to add
            pass

    print('{0} teardrops inserted'.format(count))

def __RemoveTeardropsInList(pcb, tdlist):
    """Remove all teardrops mentioned in the list if available in current PCB.
       Returns number of deleted pads"""
    to_remove=[]
    for line in tdlist:
        for z in [ pcb.GetArea(i) for i in range(pcb.GetAreaCount()) ]:
            corners = [str(z.GetCornerPosition(i)) for i in range(z.GetNumCorners())]
            corners.sort()
            if line.rstrip() == z.GetLayerName() + ':' + ''.join(corners):
                to_remove.append(z)

    count = len(to_remove)
    for tbr in to_remove:
        pcb.Remove(tbr)
    #Remove the td file
    try:
        os.remove(pcb.GetFileName() + '_td')
    except OSError:
        pass

    return count

def __RemoveSelectedTeardrops(pcb, tdlist, sel):
    """Remove only the selected teardrops if mentionned in teardrops file.
       Also update the teardrops file"""
    print('Not implemented yet')
    return 0

def RmTeardrops():
    """Remove teardrops according to teardrops definition file"""

    pcb = GetBoard()
    td_filename = pcb.GetFileName() + '_td'
    viasfile = __File2List(td_filename)
    vias_selected = __GetAllVias(pcb)[1] + __GetAllPads(pcb, [PAD_STANDARD])[1]

    if len(vias_selected) > 0:
        #Only delete selected teardrops. We need to recompute the via structure
        #in order to found it in the viasfile and delete it
        count = __RemoveSelectedTeardrops(pcb, viasfile, vias_selected)
    else:
        #Delete every teardrops mentionned in the teardrops file
        count = __RemoveTeardropsInList(pcb, viasfile)

    print('{0} teardrops removed'.format(count))

if __name__ == '__main__':
    """This part fixes polygon closing parenthis"""
    parser = argparse.ArgumentParser(description='Fix kicad pcb for teardrops')
    parser.add_argument('pcbfile', metavar='F', type=str, help='file to fix')
    args = parser.parse_args()

    state = 'SEARCH'
    for line in fileinput.FileInput(args.pcbfile, inplace=True):
        if state == 'SEARCH':
            if '(polygon' in line:
                state = 'COUNTING'
                delta = 1
        elif state == 'COUNTING':
            if ('(filled_polygon' in line) and (delta > 0):
                print('    )')
                state = 'SEARCH'
            if ('(zone (' in line) and (delta == 0):
                print('    )')
                state = 'SEARCH'
            else:
                delta = delta + line.count('(') - line.count(')')
        print(line.rstrip())
