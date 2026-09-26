#ifndef MAP_GEOMETRY_2D_H
#define MAP_GEOMETRY_2D_H
#include <boost/property_tree/json_parser.hpp>
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace env {
// Shared JSON contract. Coordinates are metres in frame map; obstacles extend
// through the planning Z range for this planar, disk-robot problem.
struct MapGeometry2D {
  using Point = std::pair<double, double>;
  using Polygon = std::vector<Point>;
  Polygon boundary;
  std::vector<Polygon> obstacles;
  Point start, goal, minimum, maximum;
  double clearance = 0.0;
  static Point readPoint(const boost::property_tree::ptree &p) {
    if (p.size() != 2) throw std::runtime_error("Map points must have exactly two coordinates");
    auto it=p.begin(); double x=(it++)->second.get_value<double>(); double y=it->second.get_value<double>();
    if (!std::isfinite(x) || !std::isfinite(y)) throw std::runtime_error("Non-finite map coordinate");
    return {x,y};
  }
  static Polygon readPolygon(const boost::property_tree::ptree &p) {
    Polygon result; for (const auto &v:p) result.push_back(readPoint(v.second));
    if (result.size()<3) throw std::runtime_error("Polygon needs at least 3 vertices");
    return result;
  }
  void load(const std::string &path) {
    boost::property_tree::ptree root; boost::property_tree::read_json(path,root);
    boundary=readPolygon(root.get_child("map.boundary")); obstacles.clear();
    for (const auto &p:root.get_child("map.obstacles")) obstacles.push_back(readPolygon(p.second));
    validateGeometry();
    start=readPoint(root.get_child("map.start")); goal=readPoint(root.get_child("map.goal"));
    double radius=root.get<double>("map.robot_radius",0), margin=root.get<double>("map.safety_margin",0);
    if (!std::isfinite(radius) || !std::isfinite(margin) || radius<0 || margin<0)
      throw std::runtime_error("Invalid robot radius or margin");
    clearance=radius+margin; minimum=maximum=boundary.front();
    for (auto p:boundary) {
      minimum.first=std::min(minimum.first,p.first); minimum.second=std::min(minimum.second,p.second);
      maximum.first=std::max(maximum.first,p.first); maximum.second=std::max(maximum.second,p.second);
    }
    if (!valid(start) || !valid(goal)) throw std::runtime_error("Map start/goal violates free space or robot clearance");
  }
  static double cross(Point a,Point b,Point c) {
    return (b.first-a.first)*(c.second-a.second)-(b.second-a.second)*(c.first-a.first);
  }
  static double distance(Point a,Point b) { return std::hypot(a.first-b.first,a.second-b.second); }
  static double pointSegment(Point p,Point a,Point b) {
    double dx=b.first-a.first,dy=b.second-a.second, l=dx*dx+dy*dy;
    double t=l>0 ? std::max(0.0,std::min(1.0,((p.first-a.first)*dx+(p.second-a.second)*dy)/l)) : 0;
    return distance(p,{a.first+t*dx,a.second+t*dy});
  }
  static bool inside(Point p,const Polygon &poly) {
    bool result=false;
    for (size_t i=0,j=poly.size()-1;i<poly.size();j=i++) {
      auto a=poly[j],b=poly[i];
      if (pointSegment(p,a,b)<1e-10) return true;
      if ((a.second>p.second)!=(b.second>p.second) &&
          p.first<(b.first-a.first)*(p.second-a.second)/(b.second-a.second)+a.first) result=!result;
    }
    return result;
  }
  static double segmentDistance(Point a,Point b,Point c,Point d) {
    double ab_c=cross(a,b,c),ab_d=cross(a,b,d),cd_a=cross(c,d,a),cd_b=cross(c,d,b);
    if (((ab_c>0 && ab_d<0)||(ab_c<0 && ab_d>0)) &&
        ((cd_a>0 && cd_b<0)||(cd_a<0 && cd_b>0))) return 0;
    return std::min(std::min(pointSegment(a,c,d),pointSegment(b,c,d)),
                    std::min(pointSegment(c,a,b),pointSegment(d,a,b)));
  }
  static void validatePolygon(const Polygon &poly) {
    if(poly.size()<3) throw std::runtime_error("Polygon needs at least 3 points");
    double twice_area=0;
    for(size_t i=0;i<poly.size();++i) {
      auto a=poly[i],b=poly[(i+1)%poly.size()];
      if(distance(a,b)<1e-10) throw std::runtime_error("Duplicate consecutive polygon vertices");
      twice_area+=cross(poly[0],a,b);
      for(size_t j=i+1;j<poly.size();++j) {
        if(j==i+1 || (i==0 && j==poly.size()-1)) continue;
        if(segmentDistance(a,b,poly[j],poly[(j+1)%poly.size()])<1e-10)
          throw std::runtime_error("Self-intersecting polygon");
      }
    }
    if(std::abs(twice_area)<1e-10) throw std::runtime_error("Zero-area polygon");
  }
  static bool ringsTouch(const Polygon &a,const Polygon &b) {
    for(size_t i=0;i<a.size();++i) for(size_t j=0;j<b.size();++j)
      if(segmentDistance(a[i],a[(i+1)%a.size()],b[j],b[(j+1)%b.size()])<1e-10) return true;
    return false;
  }
  void validateGeometry() const {
    validatePolygon(boundary);
    for(size_t i=0;i<obstacles.size();++i) {
      const auto &p=obstacles[i];validatePolygon(p);
      if(!inside(p.front(),boundary) || ringsTouch(p,boundary))
        throw std::runtime_error("Obstacle must be strictly inside boundary");
      for(size_t j=0;j<i;++j)
        if(ringsTouch(p,obstacles[j]) || inside(p.front(),obstacles[j]) || inside(obstacles[j].front(),p))
          throw std::runtime_error("Obstacles must not overlap or touch");
    }
  }
  double pointClearance(Point p) const {
    double result=std::numeric_limits<double>::infinity();
    auto visit=[&](const Polygon &poly) { for(size_t i=0;i<poly.size();++i)
      result=std::min(result,pointSegment(p,poly[i],poly[(i+1)%poly.size()])); };
    visit(boundary); for(const auto &poly:obstacles) visit(poly); return result;
  }
  bool valid(Point p) const {
    if (!std::isfinite(p.first) || !std::isfinite(p.second) || !inside(p,boundary)) return false;
    for(const auto &poly:obstacles) if(inside(p,poly)) return false;
    double c=pointClearance(p);
    return c>1e-10 && c+1e-9>=clearance;
  }
  bool segmentValid(Point a,Point b) const {
    if (!valid(a) || !valid(b)) return false;
    auto clear=[&](const Polygon &poly) { for(size_t i=0;i<poly.size();++i) {
      double d=segmentDistance(a,b,poly[i],poly[(i+1)%poly.size()]);
      if(d<1e-10 || d+1e-9<clearance) return false;
    } return true; };
    if(!clear(boundary)) return false;
    for(const auto &poly:obstacles) if(!clear(poly)) return false;
    return true;
  }
};
}
#endif
