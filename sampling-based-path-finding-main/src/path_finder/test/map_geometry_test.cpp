#include <gtest/gtest.h>
#include <occ_grid/map_geometry.h>
using env::MapGeometry2D;

MapGeometry2D room() {
  MapGeometry2D m;
  m.boundary={{0,0},{10,0},{10,10},{0,10}};
  m.obstacles={{{4,4},{6,4},{6,6},{4,6}}};m.clearance=.3;
  return m;
}
TEST(MapGeometry, DiskClearanceAndCrossing) {
  auto m=room();
  EXPECT_TRUE(m.valid({1,1}));
  EXPECT_FALSE(m.valid({4.1,5}));
  EXPECT_FALSE(m.valid({3.8,5}));
  EXPECT_TRUE(m.valid({3.7,5}));
  EXPECT_FALSE(m.valid({.2,5}));
  EXPECT_FALSE(m.segmentValid({1,5},{9,5}));
  EXPECT_FALSE(m.segmentValid({1,3.8},{9,3.8}));
  EXPECT_TRUE(m.segmentValid({1,3.6},{9,3.6}));
}
TEST(MapGeometry, ConcaveBoundaryAndEmptyObstacles) {
  MapGeometry2D m;
  m.boundary={{0,0},{4,0},{4,1},{1,1},{1,4},{0,4}};m.clearance=.1;
  EXPECT_TRUE(m.valid({.5,3}));EXPECT_TRUE(m.valid({3,.5}));
  EXPECT_FALSE(m.segmentValid({.5,3},{3,.5}));
  EXPECT_TRUE(m.segmentValid({.5,3},{.5,.5}));
}
TEST(MapGeometry, ZeroLengthAndBoundaryContact) {
  auto m=room();
  EXPECT_TRUE(m.segmentValid({1,1},{1,1}));
  m.clearance=0;
  EXPECT_FALSE(m.segmentValid({1,4},{9,4}));
  EXPECT_FALSE(m.valid({0,0}));
}
TEST(MapGeometry, RejectMalformedGeometry) {
  auto m=room();EXPECT_NO_THROW(m.validateGeometry());
  m.obstacles.push_back({{5,5},{7,5},{7,7},{5,7}});
  EXPECT_THROW(m.validateGeometry(),std::runtime_error);
  m=room();m.boundary={{0,0},{4,4},{0,4},{4,0}};
  EXPECT_THROW(m.validateGeometry(),std::runtime_error);
}

TEST(MapGeometry, PointRobotConfigurationSpaceBoundaries) {
  auto m=room();
  EXPECT_FALSE(m.valid({3.75,5.0}));       // inside radius+margin inflated obstacle
  EXPECT_TRUE(m.valid({3.69,5.0}));
  EXPECT_FALSE(m.segmentValid({1,3.75},{9,3.75}));
  EXPECT_FALSE(m.valid({0.29,2.0}));       // workspace exterior is inflated inward
  EXPECT_TRUE(m.valid({0.31,2.0}));
}

TEST(MapGeometry, CorridorNarrowerThanDiameterIsBlocked) {
  MapGeometry2D m;
  m.boundary={{0,0},{5,0},{5,5},{0,5}};
  m.obstacles={{{0.1,2.0},{4.9,2.0},{4.9,2.4},{0.1,2.4}},
               {{0.1,2.9},{4.9,2.9},{4.9,3.3},{0.1,3.3}}};
  m.clearance=.3;
  EXPECT_FALSE(m.valid({2.5,2.65}));       // 0.5 m gap < 2 * 0.3 m
}

TEST(MapGeometry, BoundaryTangentObstacleKeepsCollisionChecks) {
  auto m=room();
  m.obstacles={{{0,5},{2,4},{2,6}}};
  EXPECT_NO_THROW(m.validateGeometry());
  EXPECT_FALSE(m.valid({0,5}));
  EXPECT_FALSE(m.valid({1,5}));
  EXPECT_FALSE(m.segmentValid({1,3},{1,7}));
  EXPECT_TRUE(m.segmentValid({3,3},{3,7}));
  // Edge contact is also contained; it must not create a passage along a wall.
  m.obstacles={{{0,4},{2,4},{2,6},{0,6}}};
  EXPECT_NO_THROW(m.validateGeometry());
  EXPECT_FALSE(m.segmentValid({0,3},{0,7}));
  m.obstacles={{{-1,4},{2,4},{2,6},{-1,6}}};
  EXPECT_THROW(m.validateGeometry(),std::runtime_error);
}

TEST(MapGeometry, RejectObstacleEdgeLeavingConcaveBoundary) {
  MapGeometry2D m;
  m.boundary={{0,0},{6,0},{6,6},{4,6},{4,2},{2,2},{2,6},{0,6}};
  m.obstacles={{{1,4},{5,4},{3,1}}};
  for(auto p:m.obstacles.front()) EXPECT_TRUE(MapGeometry2D::inside(p,m.boundary));
  EXPECT_THROW(m.validateGeometry(),std::runtime_error);
}
