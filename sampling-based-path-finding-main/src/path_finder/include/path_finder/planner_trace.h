#ifndef PLANNER_TRACE_H
#define PLANNER_TRACE_H
#include <Eigen/Eigen>
#include <ros/ros.h>
#include <visualization_msgs/MarkerArray.h>
#include <std_srvs/Trigger.h>
#include <string>
#include <vector>
#include <map>
#include <array>

namespace path_plan {
// Capture real events during planning; replay afterwards so human waiting does
// not consume the search-time budget. This is a replay, not algorithm pausing.
class PlannerTrace {
  struct Event { std::string phase; Eigen::Vector3d a,b; };
  std::vector<Event> events_;
  std::map<std::array<double,3>,Eigen::Vector3d> parents_;
  size_t cursor_=0, dropped_=0;
  bool enabled_=false;
  ros::Publisher publisher_;
  ros::ServiceServer next_service_;
  ros::Timer timer_;
public:
  static PlannerTrace &instance() { static PlannerTrace trace; return trace; }
  void init(ros::NodeHandle &nh) {
    nh.param("step_mode",enabled_,false);
    publisher_=nh.advertise<visualization_msgs::MarkerArray>("steps",1,true);
    next_service_=nh.advertiseService("next_step",&PlannerTrace::next,this);
    double interval; nh.param("replay_interval",interval,0.0);
    if(interval>0) timer_=nh.createTimer(ros::Duration(interval),&PlannerTrace::tick,this);
  }
  void reset() {
    events_.clear();parents_.clear();cursor_=dropped_=0;
    visualization_msgs::MarkerArray msg; visualization_msgs::Marker clear;
    clear.action=visualization_msgs::Marker::DELETEALL;msg.markers.push_back(clear);publisher_.publish(msg);
  }
  void record(const std::string &phase,const Eigen::Vector3d &a,const Eigen::Vector3d &b) {
    if(!enabled_ || !a.allFinite() || !b.allFinite()) return;
    if(events_.size()<10000) events_.push_back({phase,a,b}); else ++dropped_;
  }
  void ready() { if(enabled_) ROS_INFO_STREAM("[Replay] " << events_.size() << " events; dropped=" << dropped_
    << ". Call ~next_step (or use replay_interval). Playback is after planning, not live pausing."); }
  bool next(std_srvs::Trigger::Request &,std_srvs::Trigger::Response &response) {
    if(cursor_>=events_.size()) {response.success=false;response.message="No more recorded events";return true;}
    const auto &e=events_[cursor_++];
    visualization_msgs::MarkerArray msg;
    visualization_msgs::Marker m; m.header.frame_id="map";m.header.stamp=ros::Time::now();m.ns="step";
    m.action=visualization_msgs::Marker::ADD;m.pose.orientation.w=1;m.id=0;
    m.type=visualization_msgs::Marker::SPHERE;m.pose.position.x=e.b.x();m.pose.position.y=e.b.y();m.pose.position.z=e.b.z();
    m.scale.x=m.scale.y=m.scale.z=0.12;m.color.a=1;m.color.r=1;m.color.g=0.65;msg.markers.push_back(m);
    m.id=1;m.type=visualization_msgs::Marker::LINE_LIST;m.pose.position=geometry_msgs::Point();
    m.scale.x=0.025; geometry_msgs::Point a,b;a.x=e.a.x();a.y=e.a.y();a.z=e.a.z();b.x=e.b.x();b.y=e.b.y();b.z=e.b.z();
    m.points={a,b};m.color.g=e.phase=="collision_reject" ? 0.0 : 0.8;msg.markers.push_back(m);
    m.id=2;m.type=visualization_msgs::Marker::TEXT_VIEW_FACING;m.points.clear();m.pose.position=b;m.pose.position.z+=0.4;
    m.scale.z=0.20;m.color.r=m.color.g=m.color.b=1;
    m.text=std::to_string(cursor_)+"/"+std::to_string(events_.size())+" "+e.phase;msg.markers.push_back(m);
    const std::string description=m.text;
    if(e.phase=="add_node" || e.phase=="rewire") parents_[{{e.b.x(),e.b.y(),e.b.z()}}]=e.a;
    m.id=3;m.type=visualization_msgs::Marker::LINE_LIST;m.pose.position=geometry_msgs::Point();
    m.points.clear();m.scale.x=.015;m.color.r=.2;m.color.g=.5;m.color.b=1;
    for(const auto &entry:parents_) {
      geometry_msgs::Point parent,child;
      parent.x=entry.second.x();parent.y=entry.second.y();parent.z=entry.second.z();
      child.x=entry.first[0];child.y=entry.first[1];child.z=entry.first[2];
      m.points.push_back(parent);m.points.push_back(child);
    }
    if(parents_.empty()) m.action=visualization_msgs::Marker::DELETE;
    msg.markers.push_back(m);
    publisher_.publish(msg);response.success=true;response.message=description;ROS_INFO_STREAM("[Replay] "<<description);return true;
  }
  void tick(const ros::TimerEvent &) {std_srvs::Trigger::Request q;std_srvs::Trigger::Response r;next(q,r);}
};
}
#endif
