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
#ifndef _BIAS_SAMPLER_
#define _BIAS_SAMPLER_

#include "convex_corridor.h"

#include <Eigen/Eigen>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

class BiasSampler
{
public:
  BiasSampler()
  {
    std::random_device rd;
    gen_ = std::mt19937_64(rd());
    uniform_rand_ = std::uniform_real_distribution<double>(0.0, 1.0);
    normal_rand_ = std::normal_distribution<double>(0.0, 1.0);
    range_.setZero();
    origin_.setZero();
    informed_ = false;
    GUILD_informed_ = false;
    corridor_sampling_ = false;
    region_prior_sampling_ = false;
    corridor_z_ = 0.0;
    corridor_total_area_ = 0.0;
  };

  explicit BiasSampler(std::uint64_t seed) : BiasSampler()
  {
    setRandomSeed(seed);
  }

  void setSamplingRange(const Eigen::Vector3d origin, const Eigen::Vector3d range)
  {
    origin_ = origin;
    range_ = range;
  }

  void samplingOnce(Eigen::Vector3d &sample)
  {
    if (corridor_sampling_)
    {
      corridorSamplingOnce(sample);
    }
    else if (region_prior_sampling_)
    {
      regionPriorSamplingOnce(sample);
    }
    else if (informed_)
    {
      informedSamplingOnce(sample);
    }
    else if (GUILD_informed_)
    {
      GUILDSamplingOnce(sample);
    }
    else
    {
      uniformSamplingOnce(sample);
    }
  }

  void uniformSamplingOnce(Eigen::Vector3d &sample)
  {
    sample[0] = uniform_rand_(gen_);
    sample[1] = uniform_rand_(gen_);
    sample[2] = uniform_rand_(gen_);
    sample.array() *= range_.array();
    sample += origin_;
  };

  static double triangleArea(const Eigen::Vector2d &a,
                             const Eigen::Vector2d &b,
                             const Eigen::Vector2d &c)
  {
    return 0.5 * std::abs((b.x() - a.x()) * (c.y() - a.y()) -
                          (b.y() - a.y()) * (c.x() - a.x()));
  }

  static bool pointInConvexPolygon(const Eigen::Vector2d &point,
                                   const std::vector<Eigen::Vector2d> &polygon,
                                   double epsilon = 1e-9)
  {
    if (polygon.size() < 3)
      return false;

    int orientation = 0;
    for (std::size_t i = 0; i < polygon.size(); ++i)
    {
      const Eigen::Vector2d &a = polygon[i];
      const Eigen::Vector2d &b = polygon[(i + 1) % polygon.size()];
      const double cross = (b.x() - a.x()) * (point.y() - a.y()) -
                           (b.y() - a.y()) * (point.x() - a.x());
      if (std::abs(cross) <= epsilon)
        continue;
      const int current = cross > 0.0 ? 1 : -1;
      if (orientation == 0)
        orientation = current;
      else if (orientation != current)
        return false;
    }
    return true;
  }

  void setConvexCorridor(const std::vector<path_plan::ConvexRegion2D> &regions)
  {
    if (regions.empty())
      throw std::invalid_argument("Convex corridor must contain at least one region");

    std::vector<Triangle2D> triangles;
    std::vector<double> cumulative_areas;
    double total_area = 0.0;
    for (const auto &region : regions)
    {
      validateConvexPolygon(region);
      const Eigen::Vector2d &anchor = region.polygon[0];
      for (std::size_t i = 1; i + 1 < region.polygon.size(); ++i)
      {
        const double area = triangleArea(anchor, region.polygon[i], region.polygon[i + 1]);
        if (area <= kGeometryEpsilon)
          continue;
        triangles.push_back({anchor, region.polygon[i], region.polygon[i + 1]});
        total_area += area;
        cumulative_areas.push_back(total_area);
      }
    }
    if (!std::isfinite(total_area) || total_area <= kGeometryEpsilon || triangles.empty())
      throw std::invalid_argument("Convex corridor has no positive-area triangles");

    corridor_regions_ = regions;
    corridor_triangles_ = triangles;
    corridor_cumulative_areas_ = cumulative_areas;
    corridor_total_area_ = total_area;
    region_prior_sampling_ = false;
    prior_regions_.clear();
    corridor_sampling_ = true;
  }

  void clearConvexCorridor()
  {
    corridor_sampling_ = false;
    corridor_regions_.clear();
    corridor_triangles_.clear();
    corridor_cumulative_areas_.clear();
    corridor_total_area_ = 0.0;
  }

  void setCorridorZ(double fixed_z)
  {
    setGuidanceZ(fixed_z);
  }

  void setRegionPriorZ(double fixed_z)
  {
    setGuidanceZ(fixed_z);
  }

  void setGuidanceZ(double fixed_z)
  {
    if (!std::isfinite(fixed_z))
      throw std::invalid_argument("Guided-sampling z must be finite");
    corridor_z_ = fixed_z;
  }

  bool corridorSamplingEnabled() const
  {
    return corridor_sampling_;
  }

  void setRegionPrior(const std::vector<path_plan::ScoredConvexRegion2D> &regions)
  {
    if (regions.empty())
      throw std::invalid_argument("Region prior must contain at least one region");

    std::vector<PriorRegion> prepared_regions;
    std::vector<double> scores;
    std::set<std::string> seen_ids;
    for (const auto &region : regions)
    {
      if (!seen_ids.insert(region.id).second)
        throw std::invalid_argument("Duplicate region-prior id '" + region.id + "'");
      if (!std::isfinite(region.score) || region.score <= 0.0 || region.score > 1.0)
        throw std::invalid_argument("Region-prior score for '" + region.id +
                                    "' must be in (0, 1]");
      path_plan::ConvexRegion2D geometry{region.id, region.polygon};
      validateConvexPolygon(geometry);

      PriorRegion prepared;
      prepared.id = region.id;
      prepared.polygon = region.polygon;
      prepared.total_area = 0.0;
      const Eigen::Vector2d &anchor = region.polygon[0];
      for (std::size_t i = 1; i + 1 < region.polygon.size(); ++i)
      {
        const double area = triangleArea(anchor, region.polygon[i], region.polygon[i + 1]);
        if (area <= kGeometryEpsilon)
          continue;
        prepared.triangles.push_back({anchor, region.polygon[i], region.polygon[i + 1]});
        prepared.total_area += area;
        prepared.cumulative_areas.push_back(prepared.total_area);
      }
      if (prepared.triangles.empty() || prepared.total_area <= kGeometryEpsilon)
        throw std::invalid_argument("Region-prior polygon '" + region.id +
                                    "' has no positive-area triangles");
      prepared_regions.push_back(prepared);
      scores.push_back(region.score);
    }

    prior_regions_ = prepared_regions;
    prior_region_distribution_ =
        std::discrete_distribution<std::size_t>(scores.begin(), scores.end());
    corridor_sampling_ = false;
    corridor_regions_.clear();
    corridor_triangles_.clear();
    corridor_cumulative_areas_.clear();
    corridor_total_area_ = 0.0;
    region_prior_sampling_ = true;
  }

  void clearRegionPrior()
  {
    region_prior_sampling_ = false;
    prior_regions_.clear();
    prior_region_distribution_ = std::discrete_distribution<std::size_t>();
  }

  bool regionPriorSamplingEnabled() const
  {
    return region_prior_sampling_;
  }

  bool isInsideCorridor(const Eigen::Vector2d &point, double epsilon = 1e-9) const
  {
    for (const auto &region : corridor_regions_)
    {
      if (pointInConvexPolygon(point, region.polygon, epsilon))
        return true;
    }
    return false;
  }

  bool isInsideRegionPrior(const Eigen::Vector2d &point, double epsilon = 1e-9) const
  {
    for (const auto &region : prior_regions_)
    {
      if (pointInConvexPolygon(point, region.polygon, epsilon))
        return true;
    }
    return false;
  }

  bool validateCorridorEndpoints(const Eigen::Vector3d &start,
                                 const Eigen::Vector3d &goal,
                                 std::string *error = nullptr,
                                 double epsilon = 1e-9) const
  {
    if (!corridor_sampling_ || corridor_regions_.empty())
      return true;
    const Eigen::Vector2d start_xy(start.x(), start.y());
    const Eigen::Vector2d goal_xy(goal.x(), goal.y());
    if (!pointInConvexPolygon(start_xy, corridor_regions_.front().polygon, epsilon))
    {
      if (error)
        *error = "start is not inside the first corridor region '" +
                 corridor_regions_.front().id + "'";
      return false;
    }
    if (!pointInConvexPolygon(goal_xy, corridor_regions_.back().polygon, epsilon))
    {
      if (error)
        *error = "goal is not inside the final corridor region '" +
                 corridor_regions_.back().id + "'";
      return false;
    }
    return true;
  }

  bool validateGuidanceEndpoints(const Eigen::Vector3d &start,
                                 const Eigen::Vector3d &goal,
                                 std::string *error = nullptr,
                                 double epsilon = 1e-9) const
  {
    if (corridor_sampling_)
      return validateCorridorEndpoints(start, goal, error, epsilon);
    if (!region_prior_sampling_)
      return true;

    const Eigen::Vector2d start_xy(start.x(), start.y());
    const Eigen::Vector2d goal_xy(goal.x(), goal.y());
    if (!isInsideRegionPrior(start_xy, epsilon))
    {
      if (error)
        *error = "start is not inside any region-prior polygon";
      return false;
    }
    if (!isInsideRegionPrior(goal_xy, epsilon))
    {
      if (error)
        *error = "goal is not inside any region-prior polygon";
      return false;
    }
    return true;
  }

  void setRandomSeed(std::uint64_t seed)
  {
    gen_.seed(seed);
  }

  void informedSamplingOnce(Eigen::Vector3d &sample)
  {
    // random uniform sampling in a unit 3-ball
    Eigen::Vector3d p;
    p[0] = normal_rand_(gen_);
    p[1] = normal_rand_(gen_);
    p[2] = normal_rand_(gen_);
    double r = pow(uniform_rand_(gen_), 0.33333);
    sample = r * p.normalized();

    // transform the pt into the ellipsoid
    sample.array() *= radii_.array();
    sample = rotation_ * sample;
    sample += center_;
  }

  void GUILDSamplingOnce(Eigen::Vector3d &sample)
  {
    // random uniform sampling in a unit 3-ball
    Eigen::Vector3d p;
    p[0] = normal_rand_(gen_);
    p[1] = normal_rand_(gen_);
    p[2] = normal_rand_(gen_);
    double r = pow(uniform_rand_(gen_), 0.33333);
    sample = r * p.normalized();

    // transform the pt into the ellipsoid
    if (p[0] > 0.0)
    {
      sample.array() *= radii_s_.array();
      sample = rotation_s_ * sample;
      sample += center_s_;
    }
    else
    {
      sample.array() *= radii_g_.array();
      sample = rotation_g_ * sample;
      sample += center_g_;
    }
  }

  void setInformedTransRot(const Eigen::Vector3d &trans, const Eigen::Matrix3d &rot)
  {
    center_ = trans;
    rotation_ = rot;
  }

  void setInformedSacling(const Eigen::Vector3d &scale)
  {
    informed_ = true;
    radii_ = scale;
  }

  void setGUILDInformed(const Eigen::Vector3d &scale1, const Eigen::Vector3d &trans1, const Eigen::Matrix3d &rot1,
                        const Eigen::Vector3d &scale2, const Eigen::Vector3d &trans2, const Eigen::Matrix3d &rot2)
  {
    radii_s_ = scale1;
    center_s_ = trans1;
    rotation_s_ = rot1;
    radii_g_ = scale2;
    center_g_ = trans2;
    rotation_g_ = rot2;
  }

  void reset()
  {
    informed_ = false;
    GUILD_informed_ = false;
  }

  // (0.0 - 1.0)
  double getUniRandNum()
  {
    return uniform_rand_(gen_);
  }

private:
  struct Triangle2D
  {
    Eigen::Vector2d a;
    Eigen::Vector2d b;
    Eigen::Vector2d c;
  };

  struct PriorRegion
  {
    std::string id;
    std::vector<Eigen::Vector2d> polygon;
    std::vector<Triangle2D> triangles;
    std::vector<double> cumulative_areas;
    double total_area;
  };

  static constexpr double kGeometryEpsilon = 1e-12;

  static void validateConvexPolygon(const path_plan::ConvexRegion2D &region)
  {
    if (region.id.empty())
      throw std::invalid_argument("Corridor region id must not be empty");
    if (region.polygon.size() < 3)
      throw std::invalid_argument("Corridor region '" + region.id +
                                  "' must have at least three polygon points");

    int orientation = 0;
    for (std::size_t i = 0; i < region.polygon.size(); ++i)
    {
      const Eigen::Vector2d &a = region.polygon[i];
      const Eigen::Vector2d &b = region.polygon[(i + 1) % region.polygon.size()];
      const Eigen::Vector2d &c = region.polygon[(i + 2) % region.polygon.size()];
      if (!std::isfinite(a.x()) || !std::isfinite(a.y()))
        throw std::invalid_argument("Corridor region '" + region.id +
                                    "' has a non-finite coordinate");
      const double cross = (b.x() - a.x()) * (c.y() - b.y()) -
                           (b.y() - a.y()) * (c.x() - b.x());
      if (std::abs(cross) <= kGeometryEpsilon)
        continue;
      const int current = cross > 0.0 ? 1 : -1;
      if (orientation == 0)
        orientation = current;
      else if (orientation != current)
        throw std::invalid_argument("Corridor region '" + region.id +
                                    "' is not a convex ordered polygon");
    }
    if (orientation == 0)
      throw std::invalid_argument("Corridor region '" + region.id +
                                  "' has zero area");
  }

  void corridorSamplingOnce(Eigen::Vector3d &sample)
  {
    if (corridor_triangles_.empty() || corridor_total_area_ <= 0.0)
      throw std::logic_error("Corridor sampling is active without valid corridor data");

    const double area_draw = uniform_rand_(gen_) * corridor_total_area_;
    auto selected = std::lower_bound(corridor_cumulative_areas_.begin(),
                                     corridor_cumulative_areas_.end(), area_draw);
    std::size_t index = static_cast<std::size_t>(
        std::distance(corridor_cumulative_areas_.begin(), selected));
    if (index >= corridor_triangles_.size())
      index = corridor_triangles_.size() - 1;

    const Triangle2D &triangle = corridor_triangles_[index];
    const double root = std::sqrt(uniform_rand_(gen_));
    const double second = uniform_rand_(gen_);
    const Eigen::Vector2d point = (1.0 - root) * triangle.a +
                                  root * (1.0 - second) * triangle.b +
                                  root * second * triangle.c;
    sample << point.x(), point.y(), corridor_z_;
  }

  void regionPriorSamplingOnce(Eigen::Vector3d &sample)
  {
    if (prior_regions_.empty())
      throw std::logic_error("Region-prior sampling is active without valid prior data");

    const PriorRegion &region = prior_regions_[prior_region_distribution_(gen_)];
    const double area_draw = uniform_rand_(gen_) * region.total_area;
    auto selected = std::lower_bound(region.cumulative_areas.begin(),
                                     region.cumulative_areas.end(), area_draw);
    std::size_t index = static_cast<std::size_t>(
        std::distance(region.cumulative_areas.begin(), selected));
    if (index >= region.triangles.size())
      index = region.triangles.size() - 1;

    const Triangle2D &triangle = region.triangles[index];
    const double root = std::sqrt(uniform_rand_(gen_));
    const double second = uniform_rand_(gen_);
    const Eigen::Vector2d point = (1.0 - root) * triangle.a +
                                  root * (1.0 - second) * triangle.b +
                                  root * second * triangle.c;
    sample << point.x(), point.y(), corridor_z_;
  }

  Eigen::Vector3d range_, origin_;
  std::mt19937_64 gen_;
  std::uniform_real_distribution<double> uniform_rand_;
  std::normal_distribution<double> normal_rand_;

  // for informed sampling
  bool informed_;
  Eigen::Vector3d center_, radii_;
  Eigen::Matrix3d rotation_;

  // for GUILD informed sampling
  bool GUILD_informed_;
  Eigen::Vector3d center_s_, radii_s_;
  Eigen::Vector3d center_g_, radii_g_;
  Eigen::Matrix3d rotation_s_;
  Eigen::Matrix3d rotation_g_;

  // Strict 2D convex-region corridor sampling. This mode takes precedence over
  // uniform, informed, and GUILD sampling whenever it is enabled.
  bool corridor_sampling_;
  double corridor_z_;
  double corridor_total_area_;
  std::vector<path_plan::ConvexRegion2D> corridor_regions_;
  std::vector<Triangle2D> corridor_triangles_;
  std::vector<double> corridor_cumulative_areas_;

  // Probabilistic region-prior sampling: choose a region proportional to its
  // score, then choose a point uniformly by area inside that polygon.
  bool region_prior_sampling_;
  std::vector<PriorRegion> prior_regions_;
  std::discrete_distribution<std::size_t> prior_region_distribution_;
};

#endif
