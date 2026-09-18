#include <ros/ros.h>
#include <sensor_msgs/PointCloud2.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl_conversions/pcl_conversions.h>

#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace
{
using Point2 = std::pair<double, double>;
using Polygon = std::vector<Point2>;

bool pointInPolygon(double x, double y, const Polygon &polygon)
{
    bool inside = false;
    const std::size_t n = polygon.size();
    if (n < 3)
        return false;

    for (std::size_t i = 0, j = n - 1; i < n; j = i++)
    {
        const double xi = polygon[i].first;
        const double yi = polygon[i].second;
        const double xj = polygon[j].first;
        const double yj = polygon[j].second;

        const bool intersects =
            ((yi > y) != (yj > y)) &&
            (x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-12) + xi);
        if (intersects)
            inside = !inside;
    }
    return inside;
}

Polygon readPolygon(const boost::property_tree::ptree &node)
{
    Polygon polygon;
    for (const auto &item : node)
    {
        const auto &point_node = item.second;
        auto it = point_node.begin();
        if (it == point_node.end())
            throw std::runtime_error("Invalid polygon point");
        const double x = it->second.get_value<double>();
        ++it;
        if (it == point_node.end())
            throw std::runtime_error("Invalid polygon point");
        const double y = it->second.get_value<double>();
        polygon.emplace_back(x, y);
    }
    if (polygon.size() < 3)
        throw std::runtime_error("Obstacle polygon must have at least 3 points");
    return polygon;
}

std::vector<Polygon> loadObstacles(const std::string &map_file)
{
    boost::property_tree::ptree root;
    boost::property_tree::read_json(map_file, root);

    std::vector<Polygon> obstacles;
    for (const auto &item : root.get_child("map.obstacles"))
        obstacles.push_back(readPolygon(item.second));
    return obstacles;
}

void appendObstacleCloud(const Polygon &polygon,
                         double xy_resolution,
                         double z_min,
                         double z_max,
                         double z_resolution,
                         pcl::PointCloud<pcl::PointXYZ> &cloud)
{
    double min_x = polygon.front().first;
    double max_x = min_x;
    double min_y = polygon.front().second;
    double max_y = min_y;
    for (const auto &p : polygon)
    {
        min_x = std::min(min_x, p.first);
        max_x = std::max(max_x, p.first);
        min_y = std::min(min_y, p.second);
        max_y = std::max(max_y, p.second);
    }

    for (double x = min_x; x <= max_x + 1e-9; x += xy_resolution)
    {
        for (double y = min_y; y <= max_y + 1e-9; y += xy_resolution)
        {
            if (!pointInPolygon(x, y, polygon))
                continue;

            for (double z = z_min; z <= z_max + 1e-9; z += z_resolution)
                cloud.points.emplace_back(
                    static_cast<float>(x),
                    static_cast<float>(y),
                    static_cast<float>(z));
        }
    }
}
} // namespace

int main(int argc, char **argv)
{
    ros::init(argc, argv, "example_map_publisher");
    ros::NodeHandle nh("~");

    std::string map_file;
    nh.param<std::string>("map_file", map_file, "");
    if (map_file.empty())
    {
        ROS_FATAL("~map_file is required");
        return 1;
    }

    double xy_resolution = 0.20;
    double z_resolution = 0.20;
    double obstacle_z_min = -0.20;
    double obstacle_z_max = 1.00;
    double publish_rate = 1.0;
    nh.param("xy_resolution", xy_resolution, xy_resolution);
    nh.param("z_resolution", z_resolution, z_resolution);
    nh.param("obstacle_z_min", obstacle_z_min, obstacle_z_min);
    nh.param("obstacle_z_max", obstacle_z_max, obstacle_z_max);
    nh.param("publish_rate", publish_rate, publish_rate);

    if (xy_resolution <= 0.0 || z_resolution <= 0.0)
    {
        ROS_FATAL("Map resolutions must be positive");
        return 1;
    }

    pcl::PointCloud<pcl::PointXYZ> cloud;
    try
    {
        const auto obstacles = loadObstacles(map_file);
        for (const auto &polygon : obstacles)
            appendObstacleCloud(
                polygon,
                xy_resolution,
                obstacle_z_min,
                obstacle_z_max,
                z_resolution,
                cloud);
        ROS_INFO_STREAM("[ExampleMap] Loaded " << obstacles.size()
                        << " obstacle polygons from " << map_file);
    }
    catch (const std::exception &error)
    {
        ROS_FATAL_STREAM("[ExampleMap] Failed to load map: " << error.what());
        return 1;
    }

    cloud.width = static_cast<std::uint32_t>(cloud.points.size());
    cloud.height = 1;
    cloud.is_dense = true;

    ros::Publisher publisher =
        nh.advertise<sensor_msgs::PointCloud2>("/random_forest/all_map", 1, true);

    ros::Rate rate(std::max(0.1, publish_rate));
    while (ros::ok())
    {
        sensor_msgs::PointCloud2 message;
        pcl::toROSMsg(cloud, message);
        message.header.frame_id = "map";
        message.header.stamp = ros::Time::now();
        publisher.publish(message);
        ros::spinOnce();
        rate.sleep();
    }
    return 0;
}
