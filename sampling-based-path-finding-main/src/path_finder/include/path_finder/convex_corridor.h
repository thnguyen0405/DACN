#ifndef CONVEX_CORRIDOR_H
#define CONVEX_CORRIDOR_H

#include <Eigen/Eigen>
#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <cmath>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace path_plan
{
  struct ConvexRegion2D
  {
    std::string id;
    std::vector<Eigen::Vector2d> polygon;
  };

  struct ConvexCorridor
  {
    std::vector<std::string> sequence;
    std::vector<ConvexRegion2D> regions;
  };

  struct ScoredConvexRegion2D
  {
    std::string id;
    double score;
    std::vector<Eigen::Vector2d> polygon;
  };

  struct ConvexSamplingPrior
  {
    std::string start_region;
    std::string goal_region;
    std::vector<ScoredConvexRegion2D> regions;
  };

  struct SafePortal2D
  {
    std::string source;
    std::string target;
    Eigen::Vector2d start;
    Eigen::Vector2d end;
  };

  struct SequenceSamplingStrategy
  {
    std::string start_region;
    std::string goal_region;
    std::vector<std::string> sequence;
    std::vector<ScoredConvexRegion2D> regions;
    std::vector<SafePortal2D> portals;
    double guided_probability = 0.8;
    double portal_probability = 0.2;
  };

  inline void requireJsonArray(const boost::property_tree::ptree &node,
                               const std::string &field)
  {
    for (const auto &item : node)
    {
      if (!item.first.empty())
        throw std::runtime_error("Corridor field '" + field + "' must be a JSON array");
    }
  }

  inline ConvexCorridor loadConvexCorridor(const std::string &file_path)
  {
    if (file_path.empty())
      throw std::runtime_error("ROS parameter 'corridor_file' is empty");

    try
    {
      boost::property_tree::ptree root;
      boost::property_tree::read_json(file_path, root);

      ConvexCorridor corridor;
      std::set<std::string> seen_ids;
      const auto &sequence_node = root.get_child("sequence");
      requireJsonArray(sequence_node, "sequence");
      for (const auto &item : sequence_node)
      {
        const std::string id = item.second.get_value<std::string>();
        if (id.empty())
          throw std::runtime_error("Corridor sequence contains an empty region id");
        if (!seen_ids.insert(id).second)
          throw std::runtime_error("Corridor sequence contains duplicate region id '" + id + "'");
        corridor.sequence.push_back(id);
      }
      if (corridor.sequence.empty())
        throw std::runtime_error("Corridor sequence must not be empty");

      const auto &regions_node = root.get_child("regions");
      requireJsonArray(regions_node, "regions");
      for (const auto &region_item : regions_node)
      {
        ConvexRegion2D region;
        region.id = region_item.second.get<std::string>("id");
        const auto &polygon_node = region_item.second.get_child("polygon");
        requireJsonArray(polygon_node, "polygon");
        for (const auto &point_item : polygon_node)
        {
          requireJsonArray(point_item.second, "polygon point");
          if (point_item.second.size() != 2)
            throw std::runtime_error("Region " + region.id +
                                     " has a polygon point that is not [x, y]");
          auto coordinate = point_item.second.begin();
          const double x = coordinate->second.get_value<double>();
          ++coordinate;
          const double y = coordinate->second.get_value<double>();
          if (!std::isfinite(x) || !std::isfinite(y))
            throw std::runtime_error("Region " + region.id +
                                     " has a non-finite polygon coordinate");
          region.polygon.emplace_back(x, y);
        }
        corridor.regions.push_back(region);
      }

      if (corridor.regions.size() != corridor.sequence.size())
        throw std::runtime_error("Corridor 'regions' must match 'sequence' one-for-one");
      for (std::size_t i = 0; i < corridor.sequence.size(); ++i)
      {
        if (corridor.regions[i].id != corridor.sequence[i])
          throw std::runtime_error("Corridor regions must be in sequence order; expected " +
                                   corridor.sequence[i] + " at index " + std::to_string(i));
      }
      return corridor;
    }
    catch (const boost::property_tree::ptree_error &error)
    {
      throw std::runtime_error("Failed to parse corridor file '" + file_path +
                               "': " + error.what());
    }
  }

  inline ConvexSamplingPrior loadConvexSamplingPrior(const std::string &file_path)
  {
    if (file_path.empty())
      throw std::runtime_error("ROS parameter 'sampling_prior_file' is empty");

    try
    {
      boost::property_tree::ptree root;
      boost::property_tree::read_json(file_path, root);

      ConvexSamplingPrior prior;
      prior.start_region = root.get<std::string>("start_region");
      prior.goal_region = root.get<std::string>("goal_region");
      if (prior.start_region.empty() || prior.goal_region.empty())
        throw std::runtime_error("Sampling prior start_region and goal_region must not be empty");

      std::set<std::string> seen_ids;
      const auto &regions_node = root.get_child("regions");
      requireJsonArray(regions_node, "regions");
      for (const auto &region_item : regions_node)
      {
        ScoredConvexRegion2D region;
        region.id = region_item.second.get<std::string>("id");
        region.score = region_item.second.get<double>("score");
        if (region.id.empty())
          throw std::runtime_error("Sampling-prior region id must not be empty");
        if (!seen_ids.insert(region.id).second)
          throw std::runtime_error("Sampling prior contains duplicate region id '" + region.id + "'");
        if (!std::isfinite(region.score) || region.score < 0.0 || region.score > 1.0)
          throw std::runtime_error("Sampling-prior score for '" + region.id + "' must be in [0, 1]");

        const auto &polygon_node = region_item.second.get_child("polygon");
        requireJsonArray(polygon_node, "polygon");
        for (const auto &point_item : polygon_node)
        {
          requireJsonArray(point_item.second, "polygon point");
          if (point_item.second.size() != 2)
            throw std::runtime_error("Region " + region.id +
                                     " has a polygon point that is not [x, y]");
          auto coordinate = point_item.second.begin();
          const double x = coordinate->second.get_value<double>();
          ++coordinate;
          const double y = coordinate->second.get_value<double>();
          if (!std::isfinite(x) || !std::isfinite(y))
            throw std::runtime_error("Region " + region.id +
                                     " has a non-finite polygon coordinate");
          region.polygon.emplace_back(x, y);
        }
        prior.regions.push_back(region);
      }
      if (prior.regions.empty())
        throw std::runtime_error("Sampling prior must contain at least one region");

      double total_score = 0.0;
      for (const auto &region : prior.regions) total_score += region.score;
      if (total_score <= 0.0)
        throw std::runtime_error("Sampling prior must contain at least one positive score");

      bool start_known = false;
      bool goal_known = false;
      for (const auto &region : prior.regions)
      {
        start_known = start_known || region.id == prior.start_region;
        goal_known = goal_known || region.id == prior.goal_region;
      }
      if (!start_known || !goal_known)
        throw std::runtime_error("Sampling-prior start_region and goal_region must exist in regions");
      return prior;
    }
    catch (const boost::property_tree::ptree_error &error)
    {
      throw std::runtime_error("Failed to parse sampling-prior file '" + file_path +
                               "': " + error.what());
    }
  }

  inline SequenceSamplingStrategy loadSequenceSamplingStrategy(const std::string &file_path)
  {
    if (file_path.empty())
      throw std::runtime_error("ROS parameter 'sequence_strategy_file' is empty");
    try
    {
      boost::property_tree::ptree root;
      boost::property_tree::read_json(file_path, root);
      SequenceSamplingStrategy strategy;
      strategy.start_region = root.get<std::string>("start_region");
      strategy.goal_region = root.get<std::string>("goal_region");
      strategy.guided_probability = root.get<double>("guided_probability", 0.8);
      strategy.portal_probability = root.get<double>("portal_probability_within_guidance", 0.2);
      if (!std::isfinite(strategy.guided_probability) || strategy.guided_probability < 0.0 || strategy.guided_probability > 1.0 ||
          !std::isfinite(strategy.portal_probability) || strategy.portal_probability < 0.0 || strategy.portal_probability > 1.0)
        throw std::runtime_error("Sequence guidance probabilities must be in [0, 1]");

      std::set<std::string> seen;
      const auto &sequence_node = root.get_child("sequence");
      requireJsonArray(sequence_node, "sequence");
      for (const auto &item : sequence_node)
      {
        const std::string id = item.second.get_value<std::string>();
        if (id.empty() || !seen.insert(id).second)
          throw std::runtime_error("Sequence ids must be non-empty and unique");
        strategy.sequence.push_back(id);
      }
      if (strategy.sequence.empty() || strategy.start_region != strategy.sequence.front() ||
          strategy.goal_region != strategy.sequence.back())
        throw std::runtime_error("Sequence endpoints must match start_region and goal_region");

      const auto &regions_node = root.get_child("regions");
      requireJsonArray(regions_node, "regions");
      for (const auto &region_item : regions_node)
      {
        ScoredConvexRegion2D region;
        region.id = region_item.second.get<std::string>("id");
        region.score = region_item.second.get<double>("score", 1.0);
        if (!std::isfinite(region.score) || region.score < 0.0 || region.score > 1.0)
          throw std::runtime_error("Sequence-region score must be in [0, 1]");
        const auto &polygon_node = region_item.second.get_child("polygon");
        requireJsonArray(polygon_node, "polygon");
        for (const auto &point_item : polygon_node)
        {
          requireJsonArray(point_item.second, "polygon point");
          if (point_item.second.size() != 2) throw std::runtime_error("Polygon point must be [x, y]");
          auto coordinate = point_item.second.begin();
          const double x = coordinate->second.get_value<double>(); ++coordinate;
          const double y = coordinate->second.get_value<double>();
          if (!std::isfinite(x) || !std::isfinite(y)) throw std::runtime_error("Non-finite polygon coordinate");
          region.polygon.emplace_back(x, y);
        }
        strategy.regions.push_back(region);
      }
      if (strategy.regions.size() != strategy.sequence.size())
        throw std::runtime_error("Sequence regions must match sequence one-for-one");
      double total_score = 0.0;
      for (std::size_t i = 0; i < strategy.sequence.size(); ++i)
      {
        if (strategy.regions[i].id != strategy.sequence[i])
          throw std::runtime_error("Sequence regions must preserve sequence order");
        total_score += strategy.regions[i].score;
      }
      if (total_score <= 0.0) throw std::runtime_error("Sequence needs at least one positive region score");

      auto portals_optional = root.get_child_optional("portals");
      if (portals_optional)
      {
        requireJsonArray(*portals_optional, "portals");
        for (const auto &portal_item : *portals_optional)
        {
          SafePortal2D portal;
          portal.source = portal_item.second.get<std::string>("source");
          portal.target = portal_item.second.get<std::string>("target");
          const auto &segment = portal_item.second.get_child("segment");
          requireJsonArray(segment, "portal segment");
          if (segment.size() != 2) throw std::runtime_error("Portal segment needs two endpoints");
          auto endpoint = segment.begin();
          const auto first = endpoint->second; ++endpoint;
          const auto second = endpoint->second;
          requireJsonArray(first, "portal endpoint"); requireJsonArray(second, "portal endpoint");
          if (first.size() != 2 || second.size() != 2) throw std::runtime_error("Portal endpoint must be [x, y]");
          auto a = first.begin(); double ax = a->second.get_value<double>(); ++a; double ay = a->second.get_value<double>();
          auto b = second.begin(); double bx = b->second.get_value<double>(); ++b; double by = b->second.get_value<double>();
          if (!std::isfinite(ax) || !std::isfinite(ay) || !std::isfinite(bx) || !std::isfinite(by) || std::hypot(ax-bx, ay-by) <= 1e-12)
            throw std::runtime_error("Portal segment must be finite and have positive length");
          portal.start = Eigen::Vector2d(ax, ay); portal.end = Eigen::Vector2d(bx, by);
          strategy.portals.push_back(portal);
        }
        if (!strategy.portals.empty() && strategy.portals.size() + 1 != strategy.sequence.size())
          throw std::runtime_error("Sequence portals must match consecutive region pairs");
        for (std::size_t i = 0; i < strategy.portals.size(); ++i)
          if (strategy.portals[i].source != strategy.sequence[i] ||
              strategy.portals[i].target != strategy.sequence[i + 1])
            throw std::runtime_error("Sequence portal order does not match sequence");
      }
      return strategy;
    }
    catch (const boost::property_tree::ptree_error &error)
    {
      throw std::runtime_error("Failed to parse sequence strategy file '" + file_path + "': " + error.what());
    }
  }
} // namespace path_plan

#endif
