#include "path_finder/sampler.h"

#include <gtest/gtest.h>

#include <string>
#include <vector>

namespace
{
  path_plan::ConvexRegion2D square(const std::string &id,
                                   double min_x,
                                   double min_y,
                                   double max_x,
                                   double max_y)
  {
    path_plan::ConvexRegion2D region;
    region.id = id;
    region.polygon = {
        Eigen::Vector2d(min_x, min_y),
        Eigen::Vector2d(max_x, min_y),
        Eigen::Vector2d(max_x, max_y),
        Eigen::Vector2d(min_x, max_y)};
    return region;
  }

  path_plan::ScoredConvexRegion2D scoredSquare(const std::string &id,
                                               double score,
                                               double min_x,
                                               double min_y,
                                               double max_x,
                                               double max_y)
  {
    path_plan::ScoredConvexRegion2D region;
    region.id = id;
    region.score = score;
    region.polygon = square(id, min_x, min_y, max_x, max_y).polygon;
    return region;
  }
}

TEST(ConvexCorridorGeometry, PointInsideBoundaryAndOutside)
{
  const auto polygon = square("A", 0.0, 0.0, 2.0, 2.0).polygon;
  EXPECT_TRUE(BiasSampler::pointInConvexPolygon(Eigen::Vector2d(1.0, 1.0), polygon));
  EXPECT_TRUE(BiasSampler::pointInConvexPolygon(Eigen::Vector2d(2.0, 1.0), polygon));
  EXPECT_FALSE(BiasSampler::pointInConvexPolygon(Eigen::Vector2d(3.0, 1.0), polygon));
}

TEST(ConvexCorridorGeometry, TriangleArea)
{
  EXPECT_DOUBLE_EQ(6.0, BiasSampler::triangleArea(
                            Eigen::Vector2d(0.0, 0.0),
                            Eigen::Vector2d(4.0, 0.0),
                            Eigen::Vector2d(0.0, 3.0)));
}

TEST(ConvexCorridorSampling, EverySampleIsInsideAndHasFixedZ)
{
  BiasSampler sampler(123456U);
  sampler.setConvexCorridor({square("A", 0.0, 0.0, 1.0, 1.0),
                             square("B", 3.0, 0.0, 5.0, 2.0)});
  sampler.setCorridorZ(7.25);

  for (int i = 0; i < 10000; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    EXPECT_TRUE(sampler.isInsideCorridor(Eigen::Vector2d(sample.x(), sample.y())));
    EXPECT_DOUBLE_EQ(7.25, sample.z());
  }
}

TEST(ConvexCorridorSampling, CorridorTakesPrecedenceOverInformedMode)
{
  BiasSampler sampler(99U);
  sampler.setConvexCorridor({square("A", 10.0, 10.0, 11.0, 11.0)});
  sampler.setCorridorZ(2.0);
  sampler.setInformedTransRot(Eigen::Vector3d::Zero(), Eigen::Matrix3d::Identity());
  sampler.setInformedSacling(Eigen::Vector3d::Ones());

  Eigen::Vector3d sample;
  sampler.samplingOnce(sample);
  EXPECT_TRUE(sampler.isInsideCorridor(Eigen::Vector2d(sample.x(), sample.y())));
  EXPECT_DOUBLE_EQ(2.0, sample.z());
}

TEST(ConvexCorridorSampling, RegionsAreWeightedByArea)
{
  BiasSampler sampler(4242U);
  sampler.setConvexCorridor({square("small", 0.0, 0.0, 1.0, 1.0),
                             square("large", 3.0, 0.0, 5.0, 2.0)});
  int large_samples = 0;
  const int sample_count = 20000;
  for (int i = 0; i < sample_count; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    if (sample.x() >= 3.0)
      ++large_samples;
  }
  const double large_fraction = static_cast<double>(large_samples) / sample_count;
  EXPECT_GT(large_fraction, 0.76);
  EXPECT_LT(large_fraction, 0.84);
}

TEST(ConvexCorridorValidation, StartAndGoalMustMatchSequenceEnds)
{
  BiasSampler sampler(1U);
  sampler.setConvexCorridor({square("first", 0.0, 0.0, 1.0, 1.0),
                             square("last", 2.0, 0.0, 3.0, 1.0)});
  std::string error;

  EXPECT_FALSE(sampler.validateCorridorEndpoints(
      Eigen::Vector3d(1.5, 0.5, 0.0), Eigen::Vector3d(2.5, 0.5, 0.0), &error));
  EXPECT_NE(std::string::npos, error.find("start"));

  EXPECT_FALSE(sampler.validateCorridorEndpoints(
      Eigen::Vector3d(0.5, 0.5, 0.0), Eigen::Vector3d(1.5, 0.5, 0.0), &error));
  EXPECT_NE(std::string::npos, error.find("goal"));

  EXPECT_TRUE(sampler.validateCorridorEndpoints(
      Eigen::Vector3d(0.0, 0.5, 0.0), Eigen::Vector3d(3.0, 0.5, 0.0), &error));
}

TEST(ConvexCorridorValidation, InvalidCorridorIsRejected)
{
  BiasSampler sampler(1U);
  path_plan::ConvexRegion2D concave;
  concave.id = "concave";
  concave.polygon = {Eigen::Vector2d(0.0, 0.0), Eigen::Vector2d(2.0, 0.0),
                     Eigen::Vector2d(1.0, 0.5), Eigen::Vector2d(2.0, 2.0),
                     Eigen::Vector2d(0.0, 2.0)};
  EXPECT_THROW(sampler.setConvexCorridor({concave}), std::invalid_argument);
}

TEST(RegionPriorSampling, SamplesStayInsideProvidedRegionsWithFixedZ)
{
  BiasSampler sampler(2026U);
  sampler.setRegionPrior({scoredSquare("low", 0.2, 0.0, 0.0, 1.0, 1.0),
                          scoredSquare("high", 0.8, 3.0, 0.0, 4.0, 1.0)});
  sampler.setRegionPriorZ(4.5);
  for (int i = 0; i < 10000; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    EXPECT_TRUE(sampler.isInsideRegionPrior(Eigen::Vector2d(sample.x(), sample.y())));
    EXPECT_DOUBLE_EQ(4.5, sample.z());
  }
}

TEST(RegionPriorSampling, RegionChoiceIsProportionalToScoresNotArea)
{
  BiasSampler sampler(8080U);
  sampler.setRegionPrior({scoredSquare("low", 0.2, 0.0, 0.0, 1.0, 1.0),
                          scoredSquare("high", 0.8, 3.0, 0.0, 5.0, 2.0)});
  int high_samples = 0;
  const int sample_count = 20000;
  for (int i = 0; i < sample_count; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    if (sample.x() >= 3.0)
      ++high_samples;
  }
  const double high_fraction = static_cast<double>(high_samples) / sample_count;
  EXPECT_GT(high_fraction, 0.76);
  EXPECT_LT(high_fraction, 0.84);
}

TEST(RegionPriorValidation, EndpointsMayBeInAnyProvidedRegion)
{
  BiasSampler sampler(3U);
  sampler.setRegionPrior({scoredSquare("A", 0.9, 0.0, 0.0, 1.0, 1.0),
                          scoredSquare("B", 0.1, 2.0, 0.0, 3.0, 1.0)});
  std::string error;
  EXPECT_TRUE(sampler.validateGuidanceEndpoints(
      Eigen::Vector3d(2.5, 0.5, 0.0), Eigen::Vector3d(0.5, 0.5, 0.0), &error));
  EXPECT_FALSE(sampler.validateGuidanceEndpoints(
      Eigen::Vector3d(4.0, 0.5, 0.0), Eigen::Vector3d(0.5, 0.5, 0.0), &error));
  EXPECT_NE(std::string::npos, error.find("start"));
}

TEST(GuidanceModes, CorridorAndRegionPriorDoNotMix)
{
  BiasSampler sampler(7U);
  sampler.setConvexCorridor({square("corridor", 0.0, 0.0, 1.0, 1.0)});
  EXPECT_TRUE(sampler.corridorSamplingEnabled());
  EXPECT_FALSE(sampler.regionPriorSamplingEnabled());

  sampler.setRegionPrior({scoredSquare("prior", 1.0, 3.0, 0.0, 4.0, 1.0)});
  EXPECT_FALSE(sampler.corridorSamplingEnabled());
  EXPECT_TRUE(sampler.regionPriorSamplingEnabled());
}

TEST(GuidanceModes, DefaultNoneModeRetainsUniformMapSampling)
{
  BiasSampler sampler(11U);
  sampler.setSamplingRange(Eigen::Vector3d(-2.0, -3.0, -4.0),
                           Eigen::Vector3d(4.0, 6.0, 8.0));
  EXPECT_FALSE(sampler.corridorSamplingEnabled());
  EXPECT_FALSE(sampler.regionPriorSamplingEnabled());
  for (int i = 0; i < 1000; ++i)
  {
    Eigen::Vector3d sample;
    sampler.samplingOnce(sample);
    EXPECT_GE(sample.x(), -2.0);
    EXPECT_LE(sample.x(), 2.0);
    EXPECT_GE(sample.y(), -3.0);
    EXPECT_LE(sample.y(), 3.0);
    EXPECT_GE(sample.z(), -4.0);
    EXPECT_LE(sample.z(), 4.0);
  }
}
