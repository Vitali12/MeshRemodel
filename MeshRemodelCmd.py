# -*- coding: utf-8 -*-
###################################################################################
#
#  MeshRemodelCmd.py
#  
#  Copyright 2019 Mark Ganson <TheMarkster> mwganson at gmail
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  
###################################################################################

__title__   = "MeshRemodel"
__author__  = "Mark Ganson <TheMarkster>"
__url__     = "https://github.com/mwganson/MeshRemodel"
__date__    = "2019.08.21"
__version__ = "1.31"
version = 1.31

import FreeCAD, FreeCADGui, Part, os, math
from PySide import QtCore, QtGui
import Draft, DraftGeomUtils, DraftVecUtils


if FreeCAD.GuiUp:
    from FreeCAD import Gui

__dir__ = os.path.dirname(__file__)
iconPath = os.path.join( __dir__, 'Resources', 'icons' )
keepToolbar = False
windowFlags = QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint #no ? in title bar

######################################################################################
# geometry utilities

class MeshRemodelGeomUtils(object):
    """Geometry Utilities"""

#source for this block of code: https://stackoverflow.com/questions/9866452/calculate-volume-of-any-tetrahedron-given-4-points
#4 points are coplanar if the tetrahedron defined by them has volume = 0
##################################################################
    def determinant_3x3(self,m):
        """helper for isCoplanar()"""
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
                m[1][0] * (m[0][1] * m[2][2] - m[0][2] * m[2][1]) +
                m[2][0] * (m[0][1] * m[1][2] - m[0][2] * m[1][1]))


    def subtract(self, a, b):
        """ helper for isCoplanar()"""
        return (a[0] - b[0],
                a[1] - b[1],
                a[2] - b[2])

    def tetrahedron_calc_volume(self, a, b, c, d):
        """helper for isCoplanar()"""
        return (abs(self.determinant_3x3((self.subtract(a, b),
                                 self.subtract(b, c),
                                 self.subtract(c, d),
                                 ))) / 6.0)

#a = [0.0, 0.0, 0.0]
#d = [2.0, 0.0, 0.0]
#c = [0.0, 2.0, 0.0]
#b = [0.0, 0.0, 2.0]

#print(tetrahedron_calc_volume(a, b, c, d))
    def isCoplanar(self, trio, pt, tol=1e-3):
        """ isCoplanar(trio, pt, tol=1e-3)
            trio is a 3-element list of vectors, pt is a vector to test, tol is tolerance, return True if all 4 are coplanar
            test is done by creating a tetrahedron and testing its volume against tol
            a tetrahedron from 4 coplanar points should have volume ~= 0
        """
        if len(trio) != 3:
            raise Exception("MeshRemodel GeomUtils Error: isCoplanar() trio parameter must be list of 3 vectors")
        A,B,C,D = trio[0],trio[1],trio[2],pt
        vol = self.tetrahedron_calc_volume(A,B,C,D)

        if vol <= tol:
            return True
        return False

    def midpoint(self, A, B):
        """ midpoint(A, B)
            A,B are vectors, return midpoint"""   
        mid = FreeCAD.Base.Vector()
        mid.x = (A.x + B.x)/2.0
        mid.y = (A.y + B.y)/2.0
        mid.z = (A.z + B.z)/2.0
        return mid

    def dist(self, p1, p2):
        """ dist (p1, p2)
            3d distance between vectors p1 and p2"""
        return self.getDistance3d(p1[0],p1[1],p1[2],p2[0],p2[1],p2[2])

    def getDistance3d(self, x1, y1, z1, x2, y2, z2):
        """ getDistance3d(x1, y1, z1, x2, y2, z2)
            3d distance between x1,y1,z1 and x2,y2,z2 float parameters"""
        return math.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)

    def sortPoints(self,pts):
        """ sortPoints(pts)
            sort pts, a list of vectors, according to distance from one point to the next
            pts[0] is taken first, then the nearest point to it is placed at pts[1]
            then pts[1] is used to find the nearest point to it and placed at pts[2], and so on
        """
        newList = [pts[0]]
        for ii in range(0, len(pts)):
            newList.extend([self.nearestPoint(newList[ii],pts,newList)])
        return newList    

    def nearestPoint(self, pt, pts, exclude):
        """ nearestPoint(pt, pts, exclude)
            pt is a vector, pts a list of vectors
            exlude is a list of vectors to exclude from process
            return nearest point to pt in pts and not in exclude"""
        if len(pts) == 0: #should never happen
            raise Exception("MeshRemodel GeomUtils Error: nearestPoint() pts length = 0\n")
        nearest = pts[0]
        d = 10**100
        for p in pts:
            if p in exclude:
                continue
            dis = self.dist(pt, p)
            if dis < d:
                d = dis
                nearest = p
        return nearest

    def isColinear(self,A,B,C):
        """ isColinear(A, B, C)
            determine whether vectors A,B,C are colinear """
        return DraftVecUtils.isColinear([A,B,C])

    def incenter(A,B,C):
        """ incenter(A, B, C)
            return incenter (vector) of triangle at vectors A,B,C 
            incenter is center of circle fitting inside the triangle
            tangent to all 3 sides
            raises exception if A,B,C are colinear
        """

        if self.isColinear(A,B,C):
            raise Exception("MeshRemodel Error: incenter() A,B,C are colinear")

        Ax,Ay,Az = A[0],A[1],A[2] 
        Bx,By,Bz = B[0],B[1],B[2]
        Cx,Cy,Cz = C[0],C[1],C[2]
 
        a = self.dist(B,C)
        b = self.dist(C,A)
        c = self.dist(A,B)
        s = a+b+c
        
        Ix = (a*Ax+b*Bx+c*Cx)/s
        Iy = (a*Ay+b*By+c*Cy)/s
        Iz = (a*Az+b*Bz+c*Cz)/s
        I = FreeCAD.Base.Vector(Ix,Iy,Iz)
        return I

    def inradius(A,B,C):
        """ inradius(A, B, C)
            return inradius of triangle A,B,C 
            this is radius of incircle, the circle that
            fits inside the triangle, tangent to all 3 sides
        """
        return self.dist(A, self.incenter(A,B,C))

#python code below was adapted from this javascript code
#from here: https://gamedev.stackexchange.com/questions/60630/how-do-i-find-the-circumcenter-of-a-triangle-in-3d
#in a question answered by user greenthings

#function circumcenter(A,B,C) {
#    var z = crossprod(subv(C,B),subv(A,B));
#    var a=vlen(subv(A,B)),b=vlen(subv(B,C)),c=vlen(subv(C,A));
#    var r = ((b*b + c*c - a*a)/(2*b*c)) * outeradius(a,b,c);
#    return addv(midpoint(A,B),multv(normaliz(crossprod(subv(A,B),z)),r));
#}

#function outeradius(a,b,c) { /// 3 lens
#    return (a*b*c) / (4*sss_area(a,b,c));
#}

#function sss_area(a,b,c) {
#    var sp = (a+b+c)*0.5;
#    return Math.sqrt(sp*(sp-a)*(sp-b)*(sp-c));
#    //semi perimeter
#}

    def circumcenter(self,A,B,C):
        """ circumcenter(A, B, C)
            return the circumcenter of triangle A,B,C
            the circumcenter is the circle that passes through
            all 3 of the triangle's vertices
            raises exception if A,B,C are colinear
        """
        if self.isColinear(A,B,C):
            raise Exception("MeshRemodel Error: circumcenter() A,B,C are colinear")

        z = C.sub(B).cross(A.sub(B))
        a = A.sub(B).Length
        b = B.sub(C).Length
        c = C.sub(A).Length
        r = ((b*b + c*c - a*a)/(2*b*c)) * self.outerradius(a,b,c)
        return  A.sub(B).cross(z).normalize().multiply(r).add(self.midpoint(A,B))

    def outerradius(self, a, b, c):
        """ helper for circumcenter()"""
        return (a*b*c) / (4*self.sss_area(a,b,c))

    def sss_area(self,a,b,c): #semiperimeter
        """ helper for circumcenter()"""
        sp = (a+b+c)*0.5;
        return math.sqrt(sp*(sp-a)*(sp-b)*(sp-c))

    def circumradius(self, A,B,C):
        """ circumradius(A, B, C)
            returns the radius of circumcircle of triangle A,B,C
            A,B,C are vectors
            the circumcircle is the circle passing through A, B, and C

        """
        return self.dist(A, self.circumcenter(A,B,C))



gu = MeshRemodelGeomUtils()
#######################################################################################
# Settings

class MeshRemodelSettingsCommandClass(object):
    """Settings"""

    def __init__(self):
        pass       

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'Settings.png') , # the name of an icon file available in the resources
            'MenuText': "&Settings" ,
            'ToolTip' : "Workbench settings dialog"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        from PySide import QtGui
        window = QtGui.QApplication.activeWindow()
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        keep = pg.GetBool('KeepToolbar',False)
        items=["Keep the toolbar active","Do not keep the toolbar active","Change point size","Change line width","Change sketch radius precision","Change coplanar tolerance","Cancel"]
        item,ok = QtGui.QInputDialog.getItem(window,'Mesh Remodel v'+__version__,'Settings\n\nSelect the settings option\n',items,0,False,windowFlags)
        if ok and item == items[-1]:
            return
        elif ok and item == items[0]:
            keep = True
            pg.SetBool('KeepToolbar', keep)
        elif ok and item==items[1]:
            keep = False
            pg.SetBool('KeepToolbar', keep)
        elif ok and item==items[2]:
            point_size = pg.GetFloat("PointSize", 4.0)
            new_point_size,ok = QtGui.QInputDialog.getDouble(window,"Point size", "Enter point size", point_size,1,50,2)
            if ok:
                pg.SetFloat("PointSize", new_point_size)
        elif ok and item==items[3]:
            line_width = pg.GetFloat("LineWidth", 5.0)
            new_line_width,ok = QtGui.QInputDialog.getDouble(window,"Line width", "Enter line width", line_width,1,50,2)
            if ok:
                pg.SetFloat("LineWidth", new_line_width)
        elif ok and item==items[4]:
            prec = pg.GetInt("SketchRadiusPrecision", 1)
            new_prec, ok = QtGui.QInputDialog.getInt(window,"Sketch Radius Precision", "\n\
-1 = no radius constraints\n\
0 = radius constraints\n\
1-12 = decimal points to round to when constraining\n\n\
Enter new sketch radius precision", prec, -1,12,1,flags=windowFlags)
            if ok:
                pg.SetInt("SketchRadiusPrecision", new_prec)
        elif ok and item==items[5]:
            coplanar_tol = pg.GetFloat("CoplanarTolerance",.001)
            new_coplanar_tol, ok = QtGui.QInputDialog.getDouble(window,"Coplanar tolerance", "Enter coplanar tolerance\n(Only applies to internal coplanar check using Alt+Click to create coplanar points)", coplanar_tol,.0000001,1,8)
            if ok:
                pg.SetFloat("CoplanarTolerance", new_coplanar_tol)
        return
   
    def IsActive(self):
        return True

#end settings class


####################################################################################
# Create the Mesh Remodel Points Object

class MeshRemodelCreatePointsObjectCommandClass(object):
    """Create Points Object command"""

    def __init__(self):
        self.mesh = None

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreatePointsObject.png') ,
            'MenuText': "Create points &object" ,
            'ToolTip' : "Create the points object"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        point_size = pg.GetFloat("PointSize",4.0)
        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        doc.openTransaction("Create points object")

        pts=[]
        meshpts = self.mesh.Mesh.Points
        for m in meshpts:
            p = Part.Point(m.Vector)
            pts.append(p.toShape())
        Part.show(Part.makeCompound(pts),"MR_Points")
        doc.ActiveObject.ViewObject.PointSize = point_size
        doc.recompute()
        doc.commitTransaction()
        doc.recompute()
        QtGui.QApplication.restoreOverrideCursor()
        return
   
    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        elif "Mesh.Feature" not in str(type(sel[0].Object)):
            return False
        else:
            self.mesh = sel[0].Object
        return True

# end create points class
####################################################################################
# Create a coplanar points object from 3 selected points

class MeshRemodelCreateCoplanarPointsObjectCommandClass(object):
    """Create coplanar points object from 3 selected points"""

    def __init__(self):
        self.pts = []
        self.obj = None #original points object

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreateCoplanar.png') ,
            'MenuText': "Create copla&nar points object" ,
            'ToolTip' : "\
Makes coplanar points object from 3 selected points, used to define the plane\n\
Creates empty sketch and places links to external geometry to coplanar points\n\
Uses internal coplanar check, (see settings -- Coplanar tolerance)\n\
(Alt+Click to use more restrictive Draft workbench coplanar check, likely to produce fewer points.)\n\
(Shift+Click for exploded compound, compatible with Shift+B block select)"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        line_width = pg.GetFloat("LineWidth",5.0)
        point_size = pg.GetFloat("PointSize",4.0)
        coplanar_tolerance = pg.GetFloat("CoplanarTolerance", .001)
        #QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        doc.openTransaction("Create coplanar")
        modifiers = QtGui.QApplication.keyboardModifiers()
        trio = [self.pts[0],self.pts[1],self.pts[2]]
        candidates = []
        if self.obj and hasattr(self.obj,"Shape"):
            candidates = self.obj.Shape.Vertexes
        coplanar = []

        for v in candidates:
            if modifiers == QtCore.Qt.AltModifier or modifiers == QtCore.Qt.AltModifier.__or__(QtCore.Qt.ShiftModifier):
                poly = Part.makePolygon([trio[0],trio[1],trio[2],v.Point])
                if DraftGeomUtils.isPlanar(poly):
                    planar = True
                else:
                    planar = False
            else: #use our own complanar check
                if gu.isCoplanar(trio,v.Point,coplanar_tolerance):
                    planar = True
                else:
                    planar = False

            if planar:
                coplanar.append(Part.Point(v.Point).toShape())
        coplanar.extend([Part.Point(v).toShape() for v in trio])

        Part.show(Part.makeCompound(coplanar),"MR_Points_Coplanar")
        doc.ActiveObject.ViewObject.PointSize = point_size
        mr = doc.ActiveObject
        if not "Sketcher_NewSketch" in Gui.listCommands():
            Gui.activateWorkbench("SketcherWorkbench")
            Gui.activateWorkbench("MeshRemodelWorkbench")
        Gui.runCommand("Sketcher_NewSketch")
        sketch=doc.ActiveObject
        sketch.Label = mr.Name+'_Sketch'
        sketch.MapReversed = True
        for ii in range(0,len(mr.Shape.Vertexes)):
            vname = 'Vertex'+str(ii+1)
            sketch.addExternal(mr.Name, vname)
        
        doc.recompute()

        if self.obj and hasattr(self.obj,"ViewObject"):
            self.obj.ViewObject.Visibility = False
        doc.recompute()
        doc.commitTransaction()
        if modifiers == QtCore.Qt.ShiftModifier or modifiers == QtCore.Qt.ShiftModifier.__or__(QtCore.Qt.AltModifier):
            doc.openTransaction("explode coplanar points")
            import CompoundTools.Explode
            input_obj = doc.ActiveObject
            comp = CompoundTools.Explode.explodeCompound(input_obj)
            input_obj.ViewObject.hide()
            for obj in comp[1]:
                obj.ViewObject.PointSize = point_size
            doc.recompute()
            doc.commitTransaction()
        #QtGui.QApplication.restoreOverrideCursor()
        return

    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        if not hasattr(sel[0],"PickedPoints"):
            return False
        count = 0
        self.pts = []
        self.obj = sel[0].Object
        for s in sel:
            if hasattr(s,"PickedPoints"):
                p = s.PickedPoints
                for pt in s.PickedPoints:
                    self.pts.append(pt)
                    count += 1
                if len(p)==0: #might be individual part point objects
                    if len(s.Object.Shape.Vertexes)==1:
                        self.pts.append(s.Object.Shape.Vertexes[0].Point)
                        count += 1
            if count > 3:
                return False
        if count == 3:
            return True
        return False

# end create coplanar points object
####################################################################################
# Create a line from 2 selected points

class MeshRemodelCreateLineCommandClass(object):
    """Create Line from 2 selected points"""

    def __init__(self):
        self.pts = []

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreateLine.png') ,
            'MenuText': "Create &line" ,
            'ToolTip' : "Create a line from 2 selected points\n(Ctrl+Click to add midpoint)\n(Ctrl+Shift+Click for only midpoint)"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        line_width = pg.GetFloat("LineWidth",5.0)
        point_size = pg.GetFloat("PointSize",4.0)
        modifiers = QtGui.QApplication.keyboardModifiers()
        #ctrl + click to include midpoint
        #ctrl + shift + click to include only the midpoint
        #QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        doc.openTransaction("Create line")

        line = Part.makeLine(self.pts[0],self.pts[1])
        lineName = "MR_Ref"
        if not modifiers == QtCore.Qt.ControlModifier.__or__(QtCore.Qt.ShiftModifier):
            Part.show(line,"MR_Line")
            lineName = doc.ActiveObject.Name
            doc.ActiveObject.ViewObject.LineWidth=line_width
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.getObject(lineName))
            FreeCAD.Console.PrintMessage(lineName+": length = "+str(line.Length)+"\n  midpoint at "+str(gu.midpoint(self.pts[0],self.pts[1]))+"\n")
        if modifiers == QtCore.Qt.ControlModifier or modifiers == QtCore.Qt.ControlModifier.__or__(QtCore.Qt.ShiftModifier):
            Part.show(Part.Point(gu.midpoint(self.pts[0],self.pts[1])).toShape(),lineName+"_Mid")
            doc.ActiveObject.ViewObject.PointSize = point_size
        doc.recompute()
        doc.commitTransaction()
        #QtGui.QApplication.restoreOverrideCursor()
        return
   
    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        if not hasattr(sel[0],"PickedPoints"):
            return False
        count = 0
        self.pts = []
        for s in sel:
            if hasattr(s,"PickedPoints"):
                p = s.PickedPoints
                for pt in s.PickedPoints:
                    self.pts.append(pt)
                    count += 1
                    if count > 2: #avoid parsing really long lists
                        return False
        if count == 2:
            return True
        return False

# end create line class

####################################################################################
# Create a Polygon from 3 or more selected points

class MeshRemodelCreatePolygonCommandClass(object):
    """Create Polygon from 3 or more selected points"""

    def __init__(self):
        self.pts = []

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreatePolygon.png') ,
            'MenuText': "Create &Polygon" ,
            'ToolTip' : "\
Create a Polygon from 3 or more selected points\n\
Might not always be coplanar, consider using links to external geometry in a sketch\n\
(Makes individual lines, use Create wire to connect into a single wire object.)\n\
(Shift+Click to not close polygon)\n\
(Alt+Click to sort selected points)\n\
"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        line_width = pg.GetFloat("LineWidth",5.0)
        point_size = pg.GetFloat("PointSize",4.0)
        #QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        doc.openTransaction("Create polygon")
        modifiers = QtGui.QApplication.keyboardModifiers()
        if modifiers != QtCore.Qt.ShiftModifier and modifiers != QtCore.Qt.ShiftModifier.__or__(QtCore.Qt.AltModifier):
            self.pts.append(self.pts[0]) #don't close polygon on shift+click

        if modifiers == QtCore.Qt.AltModifier.__or__(QtCore.Qt.ShiftModifier) or modifiers == QtCore.Qt.AltModifier:
            poly = Part.makePolygon(gu.sortPoints(self.pts))
            lineList = self.makePolygon(gu.sortPoints(self.pts))
        else:
            poly = Part.makePolygon(self.pts)
            lineList = self.makePolygon(self.pts)

        lineObjs = []
        for line in lineList:
            Part.show(line,"MR_Line")
            doc.recompute()
            lineObjs.append(doc.ActiveObject)

        for l in lineObjs:
            l.ViewObject.LineWidth = line_width

        doc.commitTransaction()

        #QtGui.QApplication.restoreOverrideCursor()
        return

    def makePolygon(self,pts):
        """make list of lines out of the pts (vectors) list one line at a time, return the list"""
        lines=[]
        for ii in range(1,len(pts)):
            if pts[ii-1] != pts[ii]:
                lines.append(Part.makeLine(pts[ii-1],pts[ii]))
        return lines

    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        if not hasattr(sel[0],"PickedPoints"):
            return False
        count = 0
        self.pts = []
        for s in sel:
            if hasattr(s,"PickedPoints"):
                p = s.PickedPoints
                for pt in s.PickedPoints:
                    self.pts.append(pt)
                    count += 1
                if len(p)==0: #might be individual part point objects
                    if len(s.Object.Shape.Vertexes)==1:
                        self.pts.append(s.Object.Shape.Vertexes[0].Point)
                        count += 1
        if count >= 3:
            return True
        return False

# end create Polygon class
####################################################################################
# Create a BSpline from 3 or more selected points

class MeshRemodelCreateBSplineCommandClass(object):
    """Create BSpline from 3 or more selected points"""

    def __init__(self):
        self.pts = []

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreateBSpline.png') ,
            'MenuText': "Create &BSpline" ,
            'ToolTip' : "Create a BSPline from 3 or more selected points\n(Shift+Click to not close bspline)\n(Alt+Click to sort selected points)"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        line_width = pg.GetFloat("LineWidth",5.0)
        point_size = pg.GetFloat("PointSize",4.0)

        #QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        doc.openTransaction("Create BSpline")
        modifiers = QtGui.QApplication.keyboardModifiers()
        is_periodic=True
        if modifiers == QtCore.Qt.ShiftModifier or modifiers == QtCore.Qt.ShiftModifier.__or__(QtCore.Qt.AltModifier):
            is_periodic=False #don't close bspline on shift+click
        bspline = Part.BSplineCurve()
        if modifiers == QtCore.Qt.AltModifier or modifiers == QtCore.Qt.AltModifier.__or__(QtCore.Qt.ShiftModifier) or modifiers == QtCore.Qt.ShiftModifier:
            sortedPoints = gu.sortPoints(self.pts)[:-1]
            bspline.interpolate(sortedPoints,PeriodicFlag=is_periodic)
        else:
            bspline.interpolate(self.pts,PeriodicFlag=is_periodic)

        Part.show(bspline.toShape(), "MR_BSpline")
        bsplineName = doc.ActiveObject.Name
        doc.ActiveObject.ViewObject.LineWidth=line_width
        #FreeCAD.Console.PrintMessage(bsplineName+": length = "+str(bspline.Length)+"\n  Center of mass: "+str(bspline.CenterOfMass)+"\n")
        #Gui.Selection.clearSelection()
        #Gui.Selection.addSelection(doc.getObject(bsplineName))


        doc.recompute()
        doc.commitTransaction()
        #QtGui.QApplication.restoreOverrideCursor()
        return

    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        if not hasattr(sel[0],"PickedPoints"):
            return False
        count = 0
        self.pts = []
        for s in sel:
            if hasattr(s,"PickedPoints"):
                p = s.PickedPoints
                for pt in s.PickedPoints:
                    self.pts.append(pt)
                    count += 1
                if len(p)==0: #might be individual part point objects
                    if len(s.Object.Shape.Vertexes)==1:
                        self.pts.append(s.Object.Shape.Vertexes[0].Point)
                        count += 1
        if count >= 3:
            return True
        return False

# end create BSpline class

###################################################################

# Create a Circle from first 3 selected points

class MeshRemodelCreateCircleCommandClass(object):
    """Create Circle from first 3 selected points"""

    def __init__(self):
        self.pts = []

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreateCircle.png') ,
            'MenuText': "Create &circle" ,
            'ToolTip' : "Create a circle from first 3 selected points\n(Ctrl+Click to include Center point)\n(Ctrl+Shift+Click for only center)"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        line_width = pg.GetFloat("LineWidth",5.0)
        point_size = pg.GetFloat("PointSize",4.0)
        #QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)


        #add_varargs_method("makeCircle",&Module::makeCircle,
        #    "makeCircle(radius,[pnt,dir,angle1,angle2]) -- Make a circle with a given radius\n"
        #    "By default pnt=Vector(0,0,0), dir=Vector(0,0,1), angle1=0 and angle2=360"
        #);

        modifiers = QtGui.QApplication.keyboardModifiers()
        poly = Part.makePolygon(self.pts)
        #Part.show(poly)
        normal = DraftGeomUtils.getNormal(poly)
       
        A = self.pts[0]
        B = self.pts[1]
        C = self.pts[2]

        if gu.isColinear(A,B,C):
            FreeCAD.Console.PrintError("MeshRemodel Error: Cannot make arc/circle from 3 colinear points\n")
            return

        center = gu.circumcenter(A,B,C)
        radius = gu.circumradius(A,B,C)

        doc.openTransaction("Create circle")
        circle = Part.makeCircle(radius, center, normal)
        circName="MR_Ref"
        if not modifiers == QtCore.Qt.ShiftModifier.__or__(QtCore.Qt.ControlModifier):
            Part.show(circle,"MR_Circle")
            circName = doc.ActiveObject.Name
            doc.ActiveObject.ViewObject.LineWidth=line_width
            FreeCAD.Console.PrintMessage(circName+": radius = "+str(radius)+"\n  center at "+str(center)+"\n")
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.getObject(circName))
        if modifiers == QtCore.Qt.ControlModifier or modifiers==QtCore.Qt.ControlModifier.__or__(QtCore.Qt.ShiftModifier):
            Part.show(Part.Point(center).toShape(),circName+"_Ctr") #show the center point on ctrl click or shift+ctrl click
            doc.ActiveObject.ViewObject.PointSize = point_size

        doc.recompute()
        doc.commitTransaction()
        #QtGui.QApplication.restoreOverrideCursor()
        return



    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        if not hasattr(sel[0],"PickedPoints"):
            return False
        count = 0
        self.pts = []
        for s in sel:
            if hasattr(s,"PickedPoints"):
                p = s.PickedPoints
                for pt in s.PickedPoints:
                    self.pts.append(pt)
                    count += 1
                if len(p)==0: #might be individual part point objects
                    if len(s.Object.Shape.Vertexes)==1:
                        self.pts.append(s.Object.Shape.Vertexes[0].Point)
                        count += 1
        if count >= 3:
            return True
        return False

# end create circle class

####################################################################################
# Create an Arc from first 3 selected points
class MeshRemodelCreateArcCommandClass(object):

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreateArc.png') ,
            'MenuText': "Create &arc" ,
            'ToolTip' : "Create an arc from first 3 selected points\n(Ctrl+Click to include Center point)\n(Ctrl+Shift+Click for only center)"}

    def __init__(self):
        self.pts = []

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        line_width = pg.GetFloat("LineWidth",5.0)
        point_size = pg.GetFloat("PointSize",4.0)
        modifiers = QtGui.QApplication.keyboardModifiers()
        poly = Part.makePolygon(self.pts)
#        Part.show(poly)
        normal = DraftGeomUtils.getNormal(poly)
       
        A = self.pts[0]
        B = self.pts[1]
        C = self.pts[2]

        if gu.isColinear(A,B,C):
            FreeCAD.Console.PrintError("MeshRemodel Error: Cannot make arc/circle from 3 colinear points\n")
            return
        center = gu.circumcenter(A,B,C)
        radius = gu.circumradius(A,B,C)

        doc.openTransaction("Create Arc")
        arc = Part.ArcOfCircle(A,B,C)
        #on ctrl+shift click we only show center
        arcName="MR_Ref"
        if not modifiers == QtCore.Qt.ControlModifier.__or__(QtCore.Qt.ShiftModifier):
            Part.show(arc.toShape(),"MR_Arc")
            arcName = doc.ActiveObject.Name
            doc.ActiveObject.ViewObject.LineWidth=line_width
            FreeCAD.Console.PrintMessage(arcName+": radius = "+str(radius)+"\n  center at "+str(center)+"\n")
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.getObject(arcName))
        if modifiers == QtCore.Qt.ControlModifier or modifiers == QtCore.Qt.ControlModifier.__or__(QtCore.Qt.ShiftModifier):
            Part.show(Part.Point(center).toShape(),arcName+"_Ctr") #show the center point
            doc.ActiveObject.ViewObject.PointSize = point_size
        doc.recompute()
        doc.commitTransaction()
        #QtGui.QApplication.restoreOverrideCursor()
        return



    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        if not hasattr(sel[0],"PickedPoints"):
            return False
        count = 0
        self.pts = []
        for s in sel:
            if hasattr(s,"PickedPoints"):
                p = s.PickedPoints
                for pt in s.PickedPoints:
                    self.pts.append(pt)
                    count += 1
                if len(p)==0: #might be individual part point objects
                    if len(s.Object.Shape.Vertexes)==1:
                        self.pts.append(s.Object.Shape.Vertexes[0].Point)
                        count += 1
        if count >= 3:
            return True
        return False

# end create arc class

####################################################################################

# Make a sketch from selected objects
class MeshRemodelCreateSketchCommandClass(object):
    """Create sketch from selected objects"""

    def __init__(self):
        self.objs = []

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreateSketch.png') ,
            'MenuText': "Create s&ketch" ,
            'ToolTip' : "\
Create a new empty sketch, optionally attaching to selected objects, e.g. 3 points to define a plane.\n\
(Ctrl+Click to make a sketch out of selected objects, e.g. circles, polygons, etc.)\n\
(Alt+Click to make a separate sketch from each selected object, and then merge them together.)\n\
"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        modifiers = QtGui.QApplication.keyboardModifiers()
        pg = FreeCAD.ParamGet("User parameter:Plugins/MeshRemodel")
        prec = pg.GetInt("SketchRadiusPrecision", 1)

        if modifiers == QtCore.Qt.NoModifier:
            if not "Sketcher_NewSketch" in Gui.listCommands():
                Gui.activateWorkbench("SketcherWorkbench")
                Gui.activateWorkbench("MeshRemodelWorkbench")
            Gui.runCommand("Sketcher_NewSketch")
            return

        doc.openTransaction("Create sketch")
        if modifiers == QtCore.Qt.AltModifier:
            #alternative method: on alt+click make separate sketch from each object, then merge them together
            sketches=[]
            for obj in self.objs:
                sketches.append(Draft.makeSketch(obj,autoconstraints=True,radiusPrecision=prec))
            doc.recompute()
            FreeCADGui.Selection.clearSelection()
            for sk in sketches:
                if sk:
                    FreeCADGui.Selection.addSelection(sk)
            if len(sketches) >= 2:
                if not "Sketcher_NewSketch" in Gui.listCommands():
                    Gui.activateWorkbench("SketcherWorkbench")
                    Gui.activateWorkbench("MeshRemodelWorkbench")
                FreeCADGui.runCommand("Sketcher_MergeSketches")

            sketch = doc.ActiveObject
            doc.recompute()
            for sk in sketches:
                if sk:
                    doc.removeObject(sk.Name)
        elif modifiers == QtCore.Qt.ControlModifier:
            #on ctrl+click make single sketch out of selected objects
            sketch = Draft.makeSketch(self.objs,autoconstraints=True,radiusPrecision=prec)
            doc.recompute()

        for o in self.objs:
            if hasattr(o,"ViewObject"):
                o.ViewObject.Visibility=False

        doc.recompute()
        doc.commitTransaction()
        return
   
    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        count = 0
        self.objs = []
        for s in sel:
            if hasattr(s,"Object"):
                self.objs.append(s.Object)
                count += 1
        if count >= 1:
            return True
        return False

# end create sketch class
####################################################################################

# Make a wire from selected objects
class MeshRemodelCreateWireCommandClass(object):
    """Create wire from selected objects"""

    def __init__(self):
        self.objs = []

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'CreateWire.png') ,
            'MenuText': "Create &wire" ,
            'ToolTip' : "Create a wire from selected objects\n(All selected objects should be connected.)\n(Runs draft upgrade)"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        doc.openTransaction("Create wire")

        Draft.upgrade(self.objs)
        
        doc.recompute()
        for o in self.objs:
            if hasattr(o,"ViewObject"):
                o.ViewObject.Visibility=False
        doc.commitTransaction()
        #QtGui.QApplication.restoreOverrideCursor()
        return
   
    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        count = 0
        self.objs = []
        for s in sel:
            if hasattr(s,"Object"):
                self.objs.append(s.Object)
                count += 1
        if count >= 1:
            return True
        return False

# end create wire class

####################################################################################

# Merge selected sketches
class MeshRemodelMergeSketchesCommandClass(object):
    """Merge selected sketches"""

    def __init__(self):
        self.objs = []

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'MergeSketches.png') ,
            'MenuText': "&Merge sketches" ,
            'ToolTip' : "Merge selected sketches with sketcher merge sketches tool"}
 
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        #doc.openTransaction("Merge sketches")  #not needed since the command does this
        if not "Sketcher_NewSketch" in Gui.listCommands():
            Gui.activateWorkbench("SketcherWorkbench")
            Gui.activateWorkbench("MeshRemodelWorkbench")
        Gui.runCommand("Sketcher_MergeSketches")
        doc.recompute()
        for o in self.objs:
            if hasattr(o,"ViewObject"):
                o.ViewObject.Visibility=False
        #doc.commitTransaction()
        #QtGui.QApplication.restoreOverrideCursor()
        Gui.activateWorkbench("MeshRemodelWorkbench")
        return
   
    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        count = 0
        self.objs = []
        for s in sel:
            if hasattr(s,"Object"):
                if "Sketch" in s.Object.Name:
                    self.objs.append(s.Object)
                    count += 1
        if count >= 2:
            return True
        return False

# end merge sketches

####################################################################################

# validate sketch
class MeshRemodelValidateSketchCommandClass(object):
    """Validate sketch"""

    def __init__(self):
        self.objs = []

    def GetResources(self):
        return {'Pixmap'  : os.path.join( iconPath , 'ValidateSketch.png') ,
            'MenuText': "&Validate sketch" ,
            'ToolTip' : "Validate selected sketch with sketcher validate sketch tool"}
 
    def Activated(self):
        if not "Sketcher_NewSketch" in Gui.listCommands():
            Gui.activateWorkbench("SketcherWorkbench")
            Gui.activateWorkbench("MeshRemodelWorkbench")
        Gui.runCommand("Sketcher_ValidateSketch")
        return
   
    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        sel = Gui.Selection.getSelectionEx()
        if len(sel) == 0:
            return False
        count = 0
        self.objs = []
        for s in sel:
            if hasattr(s,"Object"):
                if "Sketch" in s.Object.Name:
                    self.objs.append(s.Object)
                    count += 1
        if count == 1:
            return True
        return False

# end validate sketch

##################################################################################################
# initialize

def initialize():
    if FreeCAD.GuiUp:
        Gui.addCommand("MeshRemodelCreatePointsObject", MeshRemodelCreatePointsObjectCommandClass())
        Gui.addCommand("MeshRemodelCreateCoplanarPointsObject", MeshRemodelCreateCoplanarPointsObjectCommandClass())
        Gui.addCommand("MeshRemodelCreateLine", MeshRemodelCreateLineCommandClass())
        Gui.addCommand("MeshRemodelCreatePolygon", MeshRemodelCreatePolygonCommandClass())
        Gui.addCommand("MeshRemodelCreateBSpline", MeshRemodelCreateBSplineCommandClass())
        Gui.addCommand("MeshRemodelCreateCircle", MeshRemodelCreateCircleCommandClass())
        Gui.addCommand("MeshRemodelCreateArc", MeshRemodelCreateArcCommandClass())
        Gui.addCommand("MeshRemodelCreateWire", MeshRemodelCreateWireCommandClass())
        Gui.addCommand("MeshRemodelCreateSketch", MeshRemodelCreateSketchCommandClass())
        Gui.addCommand("MeshRemodelMergeSketches", MeshRemodelMergeSketchesCommandClass())
        Gui.addCommand("MeshRemodelValidateSketch", MeshRemodelValidateSketchCommandClass())
        Gui.addCommand("MeshRemodelSettings", MeshRemodelSettingsCommandClass())


initialize()
