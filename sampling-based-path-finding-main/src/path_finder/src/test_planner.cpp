/*
Copyright (C) 2022 Hongkai Ye (kyle_yeh@163.com)
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
OF SUCH DAMAGE.
*/
#include "self_msgs_and_srvs/GlbObsRcv.h"
#include "occ_grid/occ_map.h"
#include "path_finder/rrt_sharp.h"
#include "path_finder/rrt_star.h"
#include "path_finder/rrt.h"
#include "path_finder/brrt.h"
#include "path_finder/brrt_star.h"
#include "path_finder/convex_corridor.h"
#include "visualization/visualization.hpp"

#include <ros/ros.h>
#include <geometry_msgs/PoseStamped.h>

#include <stdexcept>
#include <string>

class TesterPathFinder
{
private:
    ros::NodeHandle nh_;
    ros::Subscriber goal_sub_;
    ros::Timer execution_timer_;
    ros::ServiceClient rcv_glb_obs_client_;

    env::OccMap::Ptr env_ptr_;
    std::shared_ptr<visualization::Visualization> vis_ptr_;
    shared_ptr<path_plan::RRTSharp> rrt_sharp_ptr_;
    shared_ptr<path_plan::RRTStar> rrt_star_ptr_, informed_rrt_star_ptr_;
    shared_ptr<path_plan::RRT> rrt_ptr_;
    shared_ptr<path_plan::BRRT> brrt_ptr_;
    shared_ptr<path_plan::BRRTStar> brrt_star_ptr_;

    Eigen::Vector3d start_, goal_;

    bool run_rrt_, run_rrt_star_, run_rrt_sharp_;
    bool run_brrt_, run_brrt_star_, run_informed_rrt_star_=false;
    bool run_all_=false;
    std::string guidance_mode_;
    bool auto_goal_=false, advance_start_=false;
    path_plan::ConvexCorridor corridor_;
    path_plan::ConvexSamplingPrior sampling_prior_;

    void configureGuidance()
    {
        if (!nh_.getParam("guidance_mode", guidance_mode_))
        {
            bool legacy_corridor = false;
            nh_.param("use_convex_corridor", legacy_corridor, false);
            guidance_mode_ = legacy_corridor ? "corridor" : "none";
        }

        if (guidance_mode_ == "none")
        {
            ROS_WARN("[Guidance] Mode 'none'; planners retain their original sampling behavior.");
            return;
        }

        if (guidance_mode_ == "corridor")
        {
            std::string corridor_file;
            nh_.param<std::string>("corridor_file", corridor_file, "");
            corridor_ = path_plan::loadConvexCorridor(corridor_file);
            rrt_ptr_->setConvexCorridor(corridor_.regions);
            rrt_star_ptr_->setConvexCorridor(corridor_.regions);
            if(informed_rrt_star_ptr_) informed_rrt_star_ptr_->setConvexCorridor(corridor_.regions);
            rrt_sharp_ptr_->setConvexCorridor(corridor_.regions);
            brrt_ptr_->setConvexCorridor(corridor_.regions);
            brrt_star_ptr_->setConvexCorridor(corridor_.regions);
            ROS_INFO_STREAM("[Guidance] Hard corridor mode enabled from " << corridor_file);
            return;
        }

        if (guidance_mode_ == "region_prior")
        {
            std::string sampling_prior_file;
            nh_.param<std::string>("sampling_prior_file", sampling_prior_file, "");
            sampling_prior_ = path_plan::loadConvexSamplingPrior(sampling_prior_file);
            rrt_ptr_->setRegionPrior(sampling_prior_.regions);
            rrt_star_ptr_->setRegionPrior(sampling_prior_.regions);
            if(informed_rrt_star_ptr_) informed_rrt_star_ptr_->setRegionPrior(sampling_prior_.regions);
            rrt_sharp_ptr_->setRegionPrior(sampling_prior_.regions);
            brrt_ptr_->setRegionPrior(sampling_prior_.regions);
            brrt_star_ptr_->setRegionPrior(sampling_prior_.regions);
            ROS_INFO_STREAM("[Guidance] Region-prior mode enabled from " << sampling_prior_file);
            for (const auto &region : sampling_prior_.regions)
            {
                ROS_INFO_STREAM("[Guidance] " << region.id << " score=" << region.score);
            }
            return;
        }

        throw std::runtime_error("Invalid guidance_mode '" + guidance_mode_ +
                                 "'; expected none, corridor, or region_prior");
    }

    template <typename Regions>
    void visualizeRegionBoundaries(const Regions &regions,
                                   double z,
                                   visualization::Color color)
    {
        std::vector<std::pair<Eigen::Vector3d, Eigen::Vector3d>> boundaries;
        for (const auto &region : regions)
        {
            for (std::size_t i = 0; i < region.polygon.size(); ++i)
            {
                const Eigen::Vector2d &a = region.polygon[i];
                const Eigen::Vector2d &b = region.polygon[(i + 1) % region.polygon.size()];
                boundaries.emplace_back(Eigen::Vector3d(a.x(), a.y(), z),
                                        Eigen::Vector3d(b.x(), b.y(), z));
            }
        }
        vis_ptr_->visualize_pairline(boundaries, "guidance_regions", color, 0.025);
    }

    void visualizeGuidanceRegions(double z)
    {
        if (guidance_mode_ == "corridor")
            visualizeRegionBoundaries(corridor_.regions, z, visualization::orange);
        else if (guidance_mode_ == "region_prior")
            visualizeRegionBoundaries(sampling_prior_.regions, z, visualization::yellow);
    }

    std::shared_ptr<visualization::Visualization> plannerVisualizer(const std::string &name)
    {
        if (!run_all_) return vis_ptr_;
        // Internal tree/intermediate topics must not overwrite another method.
        ros::NodeHandle scoped(nh_, "details/" + name);
        return std::make_shared<visualization::Visualization>(scoped);
    }

public:
    TesterPathFinder(const ros::NodeHandle &nh) : nh_(nh)
    {
        std::string selected;
        nh_.param<std::string>("planner",selected,"flags");
        run_all_ = selected == "all";
        run_informed_rrt_star_ = run_all_ || selected == "informed_rrt_star";
        if(run_all_) {
            ROS_INFO("[Suite] Running six methods with guidance_mode=region_prior.");
            // Exactly the same prior for all six. Keep the ordinary RRT* and
            // the sixth informed RRT* distinct even if old params are enabled.
            nh_.setParam("guidance_mode", "region_prior");
            nh_.setParam("RRT_Star/use_informed_sampling", false);
            nh_.setParam("RRT_Star/use_GUILD_sampling", false);
            nh_.setParam("RRT_Sharp/use_informed_sampling", false);
            nh_.setParam("RRT_Sharp/use_GUILD_sampling", false);
            nh_.setParam("BRRT_Star/use_informed_sampling", false);
        }
        env_ptr_ = std::make_shared<env::OccMap>();
        env_ptr_->init(nh_);
        path_plan::PlannerTrace::instance().init(nh_);
        env_ptr_->segment_observer=[](const Eigen::Vector3d &a,const Eigen::Vector3d &b,bool valid) {
          path_plan::PlannerTrace::instance().record(valid ? "collision_clear" : "collision_reject",a,b);
        };

        vis_ptr_ = std::make_shared<visualization::Visualization>(nh_);
        vis_ptr_->registe<visualization_msgs::Marker>("start");
        vis_ptr_->registe<visualization_msgs::Marker>("goal");

        rrt_sharp_ptr_ = std::make_shared<path_plan::RRTSharp>(nh_, env_ptr_);
        rrt_sharp_ptr_->setVisualizer(plannerVisualizer("rrt_sharp"));
        vis_ptr_->registe<nav_msgs::Path>("rrt_sharp_final_path");
        vis_ptr_->registe<sensor_msgs::PointCloud2>("rrt_sharp_final_wpts");

        rrt_star_ptr_ = std::make_shared<path_plan::RRTStar>(nh_, env_ptr_);
        rrt_star_ptr_->setVisualizer(plannerVisualizer("rrt_star"));
        vis_ptr_->registe<nav_msgs::Path>("rrt_star_final_path");
        vis_ptr_->registe<sensor_msgs::PointCloud2>("rrt_star_final_wpts");
        vis_ptr_->registe<visualization_msgs::MarkerArray>("rrt_star_paths");

        rrt_ptr_ = std::make_shared<path_plan::RRT>(nh_, env_ptr_);
        rrt_ptr_->setVisualizer(plannerVisualizer("rrt"));
        vis_ptr_->registe<nav_msgs::Path>("rrt_final_path");
        vis_ptr_->registe<sensor_msgs::PointCloud2>("rrt_final_wpts");

        brrt_ptr_ = std::make_shared<path_plan::BRRT>(nh_, env_ptr_);
        brrt_ptr_->setVisualizer(plannerVisualizer("brrt"));
        vis_ptr_->registe<nav_msgs::Path>("brrt_final_path");
        vis_ptr_->registe<sensor_msgs::PointCloud2>("brrt_final_wpts");

        brrt_star_ptr_ = std::make_shared<path_plan::BRRTStar>(nh_, env_ptr_);
        brrt_star_ptr_->setVisualizer(plannerVisualizer("brrt_star"));
        vis_ptr_->registe<nav_msgs::Path>("brrt_star_final_path");
        vis_ptr_->registe<sensor_msgs::PointCloud2>("brrt_star_final_wpts");

        if(run_informed_rrt_star_) {
            informed_rrt_star_ptr_ = std::make_shared<path_plan::RRTStar>(nh_,env_ptr_,true);
            informed_rrt_star_ptr_->setVisualizer(plannerVisualizer("informed_rrt_star"));
            vis_ptr_->registe<nav_msgs::Path>("informed_rrt_star_final_path");
            vis_ptr_->registe<sensor_msgs::PointCloud2>("informed_rrt_star_final_wpts");
        }

        goal_sub_ = nh_.subscribe("/goal", 1, &TesterPathFinder::goalCallback, this);
        execution_timer_ = nh_.createTimer(ros::Duration(1), &TesterPathFinder::executionCallback, this);
        rcv_glb_obs_client_ = nh_.serviceClient<self_msgs_and_srvs::GlbObsRcv>("/pub_glb_obs");

        nh_.param("initial_start_x", start_[0], 0.0);
        nh_.param("initial_start_y", start_[1], 0.0);
        nh_.param("initial_start_z", start_[2], 0.0);

        nh_.param("run_rrt", run_rrt_, true);
        nh_.param("run_rrt_star", run_rrt_star_, true);
        nh_.param("run_rrt_sharp", run_rrt_sharp_, true);
        nh_.param("run_brrt", run_brrt_, false);
        nh_.param("run_brrt_star", run_brrt_star_, false);

        if(selected!="flags") {
          if(selected!="rrt" && selected!="rrt_star" && selected!="rrt_sharp" && selected!="brrt" && selected!="brrt_star" && selected!="informed_rrt_star" && selected!="all")
            throw std::runtime_error("planner must be all, rrt, rrt_star, rrt_sharp, brrt, brrt_star or informed_rrt_star");
          run_rrt_=run_all_ || selected=="rrt"; run_rrt_star_=run_all_ || selected=="rrt_star"; run_rrt_sharp_=run_all_ || selected=="rrt_sharp";
          run_brrt_=run_all_ || selected=="brrt"; run_brrt_star_=run_all_ || selected=="brrt_star";
        }
        bool step_mode; nh_.param("step_mode",step_mode,false);
        if(step_mode && int(run_rrt_)+int(run_rrt_star_)+int(run_rrt_sharp_)+int(run_brrt_)+int(run_brrt_star_)+int(run_informed_rrt_star_)!=1)
          throw std::runtime_error("step_mode requires exactly one planner");
        nh_.param("auto_goal",auto_goal_,false); nh_.param("advance_start",advance_start_,false);
        if(env_ptr_->usesGeometry()) {
          const auto &map=env_ptr_->geometry();
          start_.x()=map.start.first;start_.y()=map.start.second;
          goal_=Eigen::Vector3d(map.goal.first,map.goal.second,start_.z());
        } else if(auto_goal_) throw std::runtime_error("auto_goal requires map_file");
        configureGuidance();
        visualizeGuidanceRegions(start_.z());
        vis_ptr_->visualize_a_ball(start_, 0.3, "start", visualization::Color::pink);
        ROS_INFO_STREAM("[Planner] Initial start = " << start_.transpose());
    }
    ~TesterPathFinder(){};

    void goalCallback(const geometry_msgs::PoseStamped::ConstPtr &goal_msg)
    {
        if(!env_ptr_->mapValid()) { ROS_WARN("Wait for the map before setting a goal"); return; }
        if(!goal_msg->header.frame_id.empty() && goal_msg->header.frame_id!="map") {
          ROS_ERROR("Goal must be expressed in frame map"); return;
        }
        path_plan::PlannerTrace::instance().reset();
        // Clear every previous result, including results of disabled planners.
        const std::vector<Eigen::Vector3d> empty;
        for(const std::string name : {"rrt", "rrt_star", "rrt_sharp", "brrt", "brrt_star", "informed_rrt_star"}) {
          vis_ptr_->visualize_path(empty,name+"_final_path");
          vis_ptr_->visualize_pointcloud(empty,name+"_final_wpts");
        }
        goal_[0] = goal_msg->pose.position.x;
        goal_[1] = goal_msg->pose.position.y;
        goal_[2] = goal_msg->pose.position.z;
        ROS_INFO_STREAM("\n-----------------------------\ngoal rcved at " << goal_.transpose());
        visualizeGuidanceRegions(start_.z());
        vis_ptr_->visualize_a_ball(start_, 0.3, "start", visualization::Color::pink);
        vis_ptr_->visualize_a_ball(goal_, 0.3, "goal", visualization::Color::steelblue);

        // BiasSampler sampler;
        // sampler.setSamplingRange(env_ptr_->getOrigin(), env_ptr_->getMapSize());
        // vector<Eigen::Vector3d> preserved_samples;
        // for (int i = 0; i < 5000; ++i)
        // {
        //     Eigen::Vector3d rand_sample;
        //     sampler.uniformSamplingOnce(rand_sample);
        //     preserved_samples.push_back(rand_sample);
        // }
        // rrt_ptr_->setPreserveSamples(preserved_samples);
        // rrt_star_ptr_->setPreserveSamples(preserved_samples);
        // rrt_sharp_ptr_->setPreserveSamples(preserved_samples);

        bool any_success = false;

        if (run_rrt_)
        {
            const auto begin=ros::WallTime::now();
            bool rrt_res = rrt_ptr_->plan(start_, goal_);
            const double elapsed=(ros::WallTime::now()-begin).toSec();
            double length=0.0;
            if(rrt_res) {
              auto path=rrt_ptr_->getPath();
              if(path.empty() || (path.front()-start_).norm()>1e-6 || (path.back()-goal_).norm()>1e-6) rrt_res=false;
              for(size_t i=1;i<path.size();++i) {
                if(!env_ptr_->checkSegment(path[i-1],path[i],DBL_MAX)) rrt_res=false;
                length+=(path[i]-path[i-1]).norm();
              }
            }
            ROS_INFO_STREAM("[RESULT] planner=rrt guidance="<<guidance_mode_<<" success="<<rrt_res
                            <<" wall_seconds="<<elapsed<<" path_length="<<(rrt_res ? length : -1.0));
            if (rrt_res)
            {
                any_success = true;
                vector<Eigen::Vector3d> final_path = rrt_ptr_->getPath();
                vis_ptr_->visualize_path(final_path, "rrt_final_path");
                vis_ptr_->visualize_pointcloud(final_path, "rrt_final_wpts");
                vector<std::pair<double, double>> slns = rrt_ptr_->getSolutions();
                ROS_INFO_STREAM("[RRT] final path len: " << length);
            }
        }

        if (run_rrt_star_)
        {
            const auto begin=ros::WallTime::now();
            bool rrt_star_res = rrt_star_ptr_->plan(start_, goal_);
            const double elapsed=(ros::WallTime::now()-begin).toSec();
            double length=0.0;
            if(rrt_star_res) {
              auto path=rrt_star_ptr_->getPath();
              if(path.empty() || (path.front()-start_).norm()>1e-6 || (path.back()-goal_).norm()>1e-6) rrt_star_res=false;
              for(size_t i=1;i<path.size();++i) {
                if(!env_ptr_->checkSegment(path[i-1],path[i],DBL_MAX)) rrt_star_res=false;
                length+=(path[i]-path[i-1]).norm();
              }
            }
            ROS_INFO_STREAM("[RESULT] planner=rrt_star guidance="<<guidance_mode_<<" success="<<rrt_star_res
                            <<" wall_seconds="<<elapsed<<" path_length="<<(rrt_star_res ? length : -1.0));
            if (rrt_star_res)
            {
                any_success = true;
                vector<vector<Eigen::Vector3d>> routes = rrt_star_ptr_->getAllPaths();
                vis_ptr_->visualize_path_list(routes, "rrt_star_paths", visualization::blue);
                vector<Eigen::Vector3d> final_path = rrt_star_ptr_->getPath();
                vis_ptr_->visualize_path(final_path, "rrt_star_final_path");
                vis_ptr_->visualize_pointcloud(final_path, "rrt_star_final_wpts");
                vector<std::pair<double, double>> slns = rrt_star_ptr_->getSolutions();
                ROS_INFO_STREAM("[RRT*] final path len: " << length);
            }
        }

        if (run_rrt_sharp_)
        {
            const auto begin=ros::WallTime::now();
            bool rrt_sharp_res = rrt_sharp_ptr_->plan(start_, goal_);
            const double elapsed=(ros::WallTime::now()-begin).toSec();
            double length=0.0;
            if(rrt_sharp_res) {
              auto path=rrt_sharp_ptr_->getPath();
              if(path.empty() || (path.front()-start_).norm()>1e-6 || (path.back()-goal_).norm()>1e-6) rrt_sharp_res=false;
              for(size_t i=1;i<path.size();++i) {
                if(!env_ptr_->checkSegment(path[i-1],path[i],DBL_MAX)) rrt_sharp_res=false;
                length+=(path[i]-path[i-1]).norm();
              }
            }
            ROS_INFO_STREAM("[RESULT] planner=rrt_sharp guidance="<<guidance_mode_<<" success="<<rrt_sharp_res
                            <<" wall_seconds="<<elapsed<<" path_length="<<(rrt_sharp_res ? length : -1.0));
            if (rrt_sharp_res)
            {
                any_success = true;
                vector<Eigen::Vector3d> final_path = rrt_sharp_ptr_->getPath();
                vis_ptr_->visualize_path(final_path, "rrt_sharp_final_path");
                vis_ptr_->visualize_pointcloud(final_path, "rrt_sharp_final_wpts");
                vector<std::pair<double, double>> slns = rrt_sharp_ptr_->getSolutions();
                ROS_INFO_STREAM("[RRT#] final path len: " << length);
            }
        }

        if (run_brrt_)
        {
            const auto begin=ros::WallTime::now();
            bool brrt_res = brrt_ptr_->plan(start_, goal_);
            const double elapsed=(ros::WallTime::now()-begin).toSec();
            double length=0.0;
            if(brrt_res) {
              auto path=brrt_ptr_->getPath();
              if(path.empty() || (path.front()-start_).norm()>1e-6 || (path.back()-goal_).norm()>1e-6) brrt_res=false;
              for(size_t i=1;i<path.size();++i) {
                if(!env_ptr_->checkSegment(path[i-1],path[i],DBL_MAX)) brrt_res=false;
                length+=(path[i]-path[i-1]).norm();
              }
            }
            ROS_INFO_STREAM("[RESULT] planner=brrt guidance="<<guidance_mode_<<" success="<<brrt_res
                            <<" wall_seconds="<<elapsed<<" path_length="<<(brrt_res ? length : -1.0));
            if (brrt_res)
            {
                any_success = true;
                vector<Eigen::Vector3d> final_path = brrt_ptr_->getPath();
                vis_ptr_->visualize_path(final_path, "brrt_final_path");
                vis_ptr_->visualize_pointcloud(final_path, "brrt_final_wpts");
                vector<std::pair<double, double>> slns = brrt_ptr_->getSolutions();
                ROS_INFO_STREAM("[BRRT] final path len: " << length);
            }
        }

        if (run_brrt_star_)
        {
            const auto begin=ros::WallTime::now();
            bool brrt_star_res = brrt_star_ptr_->plan(start_, goal_);
            const double elapsed=(ros::WallTime::now()-begin).toSec();
            double length=0.0;
            if(brrt_star_res) {
              auto path=brrt_star_ptr_->getPath();
              if(path.empty() || (path.front()-start_).norm()>1e-6 || (path.back()-goal_).norm()>1e-6) brrt_star_res=false;
              for(size_t i=1;i<path.size();++i) {
                if(!env_ptr_->checkSegment(path[i-1],path[i],DBL_MAX)) brrt_star_res=false;
                length+=(path[i]-path[i-1]).norm();
              }
            }
            ROS_INFO_STREAM("[RESULT] planner=brrt_star guidance="<<guidance_mode_<<" success="<<brrt_star_res
                            <<" wall_seconds="<<elapsed<<" path_length="<<(brrt_star_res ? length : -1.0));
            if (brrt_star_res)
            {
                any_success = true;
                vector<Eigen::Vector3d> final_path = brrt_star_ptr_->getPath();
                vis_ptr_->visualize_path(final_path, "brrt_star_final_path");
                vis_ptr_->visualize_pointcloud(final_path, "brrt_star_final_wpts");
                vector<std::pair<double, double>> slns = brrt_star_ptr_->getSolutions();
                ROS_INFO_STREAM("[BRRT*] final path len: " << length);
            }
        }

        if (run_informed_rrt_star_)
        {
            const auto begin=ros::WallTime::now();
            bool informed_rrt_star_res = informed_rrt_star_ptr_->plan(start_, goal_);
            const double elapsed=(ros::WallTime::now()-begin).toSec();
            double length=0.0;
            if(informed_rrt_star_res) {
              auto path=informed_rrt_star_ptr_->getPath();
              if(path.empty() || (path.front()-start_).norm()>1e-6 || (path.back()-goal_).norm()>1e-6) informed_rrt_star_res=false;
              for(size_t i=1;i<path.size();++i) {
                if(!env_ptr_->checkSegment(path[i-1],path[i],DBL_MAX)) informed_rrt_star_res=false;
                length+=(path[i]-path[i-1]).norm();
              }
            }
            ROS_INFO_STREAM("[RESULT] planner=informed_rrt_star guidance="<<guidance_mode_<<" success="<<informed_rrt_star_res
                            <<" wall_seconds="<<elapsed<<" path_length="<<(informed_rrt_star_res ? length : -1.0));
            if (informed_rrt_star_res)
            {
                any_success = true;
                vector<vector<Eigen::Vector3d>> routes = informed_rrt_star_ptr_->getAllPaths();
                vis_ptr_->visualize_path_list(routes, "informed_rrt_star_paths", visualization::blue);
                vector<Eigen::Vector3d> final_path = informed_rrt_star_ptr_->getPath();
                vis_ptr_->visualize_path(final_path, "informed_rrt_star_final_path");
                vis_ptr_->visualize_pointcloud(final_path, "informed_rrt_star_final_wpts");
                vector<std::pair<double, double>> slns = informed_rrt_star_ptr_->getSolutions();
                ROS_INFO_STREAM("[Informed RRT*] final path len: " << length);
            }
        }

        if(run_all_) ROS_INFO("[Suite] All six methods finished. Toggle method groups under Planning in RViz.");
        path_plan::PlannerTrace::instance().ready();
        if (any_success && advance_start_)
        {
            start_ = goal_;
            ROS_INFO_STREAM("[Planner] At least one planner succeeded; next start = " << start_.transpose());
        }
        else if (!any_success)
        {
            ROS_WARN_STREAM("[Planner] All planners failed; keeping previous start = " << start_.transpose());
        }
    }

    void executionCallback(const ros::TimerEvent &event)
    {
        if (!env_ptr_->mapValid())
        {
            ROS_INFO("no map rcved yet.");
            self_msgs_and_srvs::GlbObsRcv srv;
            if (!rcv_glb_obs_client_.call(srv))
                ROS_WARN("Failed to call service /pub_glb_obs");
        }
        else
        {
            execution_timer_.stop();
            if(auto_goal_) {
              geometry_msgs::PoseStamped::Ptr msg(new geometry_msgs::PoseStamped);
              msg->header.frame_id="map";msg->pose.position.x=goal_.x();msg->pose.position.y=goal_.y();msg->pose.position.z=goal_.z();
              goalCallback(msg);
            }
        }
    };
};

int main(int argc, char **argv)
{
    ros::init(argc, argv, "test_path_finder_node");
    ros::NodeHandle nh("~");

    try
    {
        TesterPathFinder tester(nh);

        ros::AsyncSpinner spinner(1); // Serialize planning, new goals and trace replay.
        spinner.start();
        ros::waitForShutdown();
        return 0;
    }
    catch (const std::exception &error)
    {
        ROS_FATAL_STREAM("Failed to initialize path planner: " << error.what());
        return 1;
    }
}
