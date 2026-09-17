# Giải thích từng dòng: test_planner.cpp

ROS node demo/điều phối, không phải unit test dù tên có test. main → constructor → configureGuidance → spinner → goalCallback → từng planner.plan. executionCallback là timer xin map, không phải vòng lập kế hoạch. Năm planner được gọi tuần tự trong goalCallback.

Nguồn: [test_planner.cpp](/Users/nguyen/BK/SEM7/DACN/Motion_Planner/sampling-based-path-finding-main/src/path_finder/src/test_planner.cpp). Số dòng khớp bản đọc ngày 17/09/2026 (321 dòng). Code nguồn không bị sửa.

Bảng giữ cả dòng trống và dấu đóng/mở để bạn đối chiếu không bị lệch số dòng. Với một câu lệnh xuống nhiều dòng, đọc các dòng liền nhau như một biểu thức.

| Dòng | Code gốc | Giải thích tiếng Việt |
| --- | --- | --- |
| 1 | <code>/*</code> | Mở comment nhiều dòng cho thông tin bản quyền; compiler không thực thi phần này. |
| 2 | <code>Copyright (C) 2022 Hongkai Ye (kyle_yeh@163.com)</code> | Thông tin tác giả/bản quyền của mã nguồn gốc. |
| 3 | <code>Redistribution and use in source and binary forms, with or without</code> | Văn bản giấy phép về phân phối lại source/binary và giữ thông báo đi kèm; không tham gia flow planner. |
| 4 | <code>modification, are permitted provided that the following conditions are met:</code> | Văn bản giấy phép về phân phối lại source/binary và giữ thông báo đi kèm; không tham gia flow planner. |
| 5 | <code>1. Redistributions of source code must retain the above copyright notice, this</code> | Văn bản giấy phép về phân phối lại source/binary và giữ thông báo đi kèm; không tham gia flow planner. |
| 6 | <code>   list of conditions and the following disclaimer.</code> | Văn bản giấy phép về phân phối lại source/binary và giữ thông báo đi kèm; không tham gia flow planner. |
| 7 | <code>2. Redistributions in binary form must reproduce the above copyright notice,</code> | Văn bản giấy phép về phân phối lại source/binary và giữ thông báo đi kèm; không tham gia flow planner. |
| 8 | <code>   this list of conditions and the following disclaimer in the documentation</code> | Văn bản giấy phép về phân phối lại source/binary và giữ thông báo đi kèm; không tham gia flow planner. |
| 9 | <code>   and/or other materials provided with the distribution.</code> | Văn bản giấy phép về phân phối lại source/binary và giữ thông báo đi kèm; không tham gia flow planner. |
| 10 | <code>THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS&#x27;&#x27; AND ANY EXPRESS OR IMPLIED</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 11 | <code>WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 12 | <code>MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 13 | <code>EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 14 | <code>EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 15 | <code>OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 16 | <code>INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 17 | <code>CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 18 | <code>IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 19 | <code>OF SUCH DAMAGE.</code> | Văn bản miễn trừ bảo đảm/trách nhiệm trong comment giấy phép; không phải code xử lý lỗi. |
| 20 | <code>*/</code> | Đóng comment nhiều dòng. |
| 21 | <code>#include &quot;self_msgs_and_srvs/GlbObsRcv.h&quot;</code> | Include kiểu ROS service GlbObsRcv dùng yêu cầu phát bản đồ vật cản toàn cục. |
| 22 | <code>#include &quot;occ_grid/occ_map.h&quot;</code> | Include occupancy map và các hàm kiểm tra trạng thái/đoạn va chạm. |
| 23 | <code>#include &quot;path_finder/rrt_sharp.h&quot;</code> | Include định nghĩa planner RRT#. |
| 24 | <code>#include &quot;path_finder/rrt_star.h&quot;</code> | Include định nghĩa planner RRT*. |
| 25 | <code>#include &quot;path_finder/rrt.h&quot;</code> | Include định nghĩa planner RRT. |
| 26 | <code>#include &quot;path_finder/brrt.h&quot;</code> | Include định nghĩa planner BRRT hai hướng. |
| 27 | <code>#include &quot;path_finder/brrt_star.h&quot;</code> | Include định nghĩa planner BRRT*. |
| 28 | <code>#include &quot;path_finder/convex_corridor.h&quot;</code> | Include các cấu trúc vùng/corridor/prior và hàm đọc JSON guidance. |
| 29 | <code>#include &quot;visualization/visualization.hpp&quot;</code> | Include lớp tiện ích publish hình/đường/point cloud cho RViz. |
| 30 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 31 | <code>#include &lt;ros/ros.h&gt;</code> | Include API ROS C++: node, parameter, subscriber, timer, spinner và logging. |
| 32 | <code>#include &lt;geometry_msgs/PoseStamped.h&gt;</code> | Include message PoseStamped nhận vị trí goal. |
| 33 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 34 | <code>#include &lt;stdexcept&gt;</code> | Include std::runtime_error và họ exception chuẩn cần ở đây. |
| 35 | <code>#include &lt;string&gt;</code> | Include std::string. |
| 36 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 37 | <code>class TesterPathFinder</code> | Lớp điều phối môi trường, visualization và năm planner; không tự triển khai thuật toán RRT. |
| 38 | <code>{</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 39 | <code>private:</code> | Các thành viên bên dưới chỉ được truy cập trực tiếp từ bên trong lớp. |
| 40 | <code>    ros::NodeHandle nh_;</code> | NodeHandle dùng đọc params và tạo ROS interfaces; dấu _ là quy ước tên thành viên. |
| 41 | <code>    ros::Subscriber goal_sub_;</code> | Giữ subscription nhận goal để subscription sống cùng đối tượng. |
| 42 | <code>    ros::Timer execution_timer_;</code> | Giữ timer kiểm tra đã có bản đồ chưa. |
| 43 | <code>    ros::ServiceClient rcv_glb_obs_client_;</code> | Client gọi service yêu cầu phát bản đồ toàn cục. |
| 44 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 45 | <code>    env::OccMap::Ptr env_ptr_;</code> | Smart pointer tới occupancy map được các planner dùng chung. |
| 46 | <code>    std::shared_ptr&lt;visualization::Visualization&gt; vis_ptr_;</code> | Smart pointer tới đối tượng visualization dùng chung. |
| 47 | <code>    shared_ptr&lt;path_plan::RRTSharp&gt; rrt_sharp_ptr_;</code> | Smart pointer tới planner RRT#. |
| 48 | <code>    shared_ptr&lt;path_plan::RRTStar&gt; rrt_star_ptr_;</code> | Smart pointer tới planner RRT*. |
| 49 | <code>    shared_ptr&lt;path_plan::RRT&gt; rrt_ptr_;</code> | Smart pointer tới planner RRT. |
| 50 | <code>    shared_ptr&lt;path_plan::BRRT&gt; brrt_ptr_;</code> | Smart pointer tới planner BRRT. |
| 51 | <code>    shared_ptr&lt;path_plan::BRRTStar&gt; brrt_star_ptr_;</code> | Smart pointer tới planner BRRT*. |
| 52 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 53 | <code>    Eigen::Vector3d start_, goal_;</code> | Hai vector Eigen ba chiều chứa tọa độ start và goal trong không gian liên tục, không phải ID C0/C6. |
| 54 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 55 | <code>    bool run_rrt_, run_rrt_star_, run_rrt_sharp_;</code> | Cờ bật/tắt chạy RRT, RRT* và RRT# khi nhận goal. |
| 56 | <code>    bool run_brrt_, run_brrt_star_;</code> | Cờ bật/tắt BRRT và BRRT*. |
| 57 | <code>    std::string guidance_mode_;</code> | Chuỗi chọn none, corridor hoặc region_prior. |
| 58 | <code>    path_plan::ConvexCorridor corridor_;</code> | Giữ corridor đã đọc, gồm danh sách vùng theo route để cấu hình/vẽ. |
| 59 | <code>    path_plan::ConvexSamplingPrior sampling_prior_;</code> | Giữ prior đã đọc, gồm mọi vùng và score để cấu hình/vẽ. |
| 60 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 61 | <code>    void configureGuidance()</code> | Hàm cấu hình sampling guidance cho tất cả planner, chạy trong constructor. |
| 62 | <code>    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 63 | <code>        if (!nh_.getParam(&quot;guidance_mode&quot;, guidance_mode_))</code> | Thử đọc param guidance_mode; ! nghĩa là vào nhánh sau nếu param không tồn tại. |
| 64 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 65 | <code>            bool legacy_corridor = false;</code> | Cờ tương thích cấu hình cũ, ban đầu false. |
| 66 | <code>            nh_.param(&quot;use_convex_corridor&quot;, legacy_corridor, false);</code> | Đọc use_convex_corridor; thiếu thì false. |
| 67 | <code>            guidance_mode_ = legacy_corridor ? &quot;corridor&quot; : &quot;none&quot;;</code> | Toán tử ba ngôi: cờ cũ true→corridor, false→none. Chỉ dùng khi không có guidance_mode. |
| 68 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 69 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 70 | <code>        if (guidance_mode_ == &quot;none&quot;)</code> | Nhánh none: giữ cách lấy mẫu gốc của từng planner. |
| 71 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 72 | <code>            ROS_WARN(&quot;[Guidance] Mode &#x27;none&#x27;; planners retain their original sampling behavior.&quot;);</code> | Log mức WARN thông báo guidance bị tắt, không phải exception. |
| 73 | <code>            return;</code> | Kết thúc cấu hình; không đọc JSON guidance. |
| 74 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 75 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 76 | <code>        if (guidance_mode_ == &quot;corridor&quot;)</code> | Nhánh corridor: chỉ dùng polygon của route chọn trước. |
| 77 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 78 | <code>            std::string corridor_file;</code> | Biến chuỗi chứa đường dẫn corridor JSON. |
| 79 | <code>            nh_.param&lt;std::string&gt;(&quot;corridor_file&quot;, corridor_file, &quot;&quot;);</code> | Đọc corridor_file, mặc định rỗng; loader sẽ lỗi nếu không dùng được. |
| 80 | <code>            corridor_ = path_plan::loadConvexCorridor(corridor_file);</code> | Đọc/kiểm tra sampling_corridor.json bằng loader trong convex_corridor.h. |
| 81 | <code>            rrt_ptr_-&gt;setConvexCorridor(corridor_.regions);</code> | Cấp polygon corridor cho RRT; lời gọi chuyển tiếp xuống sampler của planner đó. |
| 82 | <code>            rrt_star_ptr_-&gt;setConvexCorridor(corridor_.regions);</code> | Cấp polygon corridor cho RRT*; lời gọi chuyển tiếp xuống sampler của planner đó. |
| 83 | <code>            rrt_sharp_ptr_-&gt;setConvexCorridor(corridor_.regions);</code> | Cấp polygon corridor cho RRT#; lời gọi chuyển tiếp xuống sampler của planner đó. |
| 84 | <code>            brrt_ptr_-&gt;setConvexCorridor(corridor_.regions);</code> | Cấp polygon corridor cho BRRT; lời gọi chuyển tiếp xuống sampler của planner đó. |
| 85 | <code>            brrt_star_ptr_-&gt;setConvexCorridor(corridor_.regions);</code> | Cấp polygon corridor cho BRRT*; lời gọi chuyển tiếp xuống sampler của planner đó. |
| 86 | <code>            ROS_INFO_STREAM(&quot;[Guidance] Hard corridor mode enabled from &quot; &lt;&lt; corridor_file);</code> | Log file đã nạp ở chế độ corridor. |
| 87 | <code>            return;</code> | Hoàn tất nhánh corridor, không chạy tiếp region_prior. |
| 88 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 89 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 90 | <code>        if (guidance_mode_ == &quot;region_prior&quot;)</code> | Nhánh ưu tiên từng vùng. |
| 91 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 92 | <code>            std::string sampling_prior_file;</code> | Biến chứa đường dẫn sampling_prior.json. |
| 93 | <code>            nh_.param&lt;std::string&gt;(&quot;sampling_prior_file&quot;, sampling_prior_file, &quot;&quot;);</code> | Đọc sampling_prior_file, mặc định chuỗi rỗng. |
| 94 | <code>            sampling_prior_ = path_plan::loadConvexSamplingPrior(sampling_prior_file);</code> | Loader đọc JSON có ID, score, polygon và thông tin start/goal. |
| 95 | <code>            rrt_ptr_-&gt;setRegionPrior(sampling_prior_.regions);</code> | Cấp danh sách vùng kèm score cho RRT; sampler chuẩn hóa score để chọn vùng. |
| 96 | <code>            rrt_star_ptr_-&gt;setRegionPrior(sampling_prior_.regions);</code> | Cấp danh sách vùng kèm score cho RRT*; sampler chuẩn hóa score để chọn vùng. |
| 97 | <code>            rrt_sharp_ptr_-&gt;setRegionPrior(sampling_prior_.regions);</code> | Cấp danh sách vùng kèm score cho RRT#; sampler chuẩn hóa score để chọn vùng. |
| 98 | <code>            brrt_ptr_-&gt;setRegionPrior(sampling_prior_.regions);</code> | Cấp danh sách vùng kèm score cho BRRT; sampler chuẩn hóa score để chọn vùng. |
| 99 | <code>            brrt_star_ptr_-&gt;setRegionPrior(sampling_prior_.regions);</code> | Cấp danh sách vùng kèm score cho BRRT*; sampler chuẩn hóa score để chọn vùng. |
| 100 | <code>            ROS_INFO_STREAM(&quot;[Guidance] Region-prior mode enabled from &quot; &lt;&lt; sampling_prior_file);</code> | Log file prior đã nạp. |
| 101 | <code>            for (const auto &amp;region : sampling_prior_.regions)</code> | Duyệt từng vùng bằng tham chiếu const để không copy và không sửa dữ liệu. |
| 102 | <code>            {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 103 | <code>                ROS_INFO_STREAM(&quot;[Guidance] &quot; &lt;&lt; region.id &lt;&lt; &quot; score=&quot; &lt;&lt; region.score);</code> | Log ID và score thô từng vùng; xác suất chuẩn hóa được tạo trong sampler. |
| 104 | <code>            }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 105 | <code>            return;</code> | Hoàn tất nhánh region_prior. |
| 106 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 107 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 108 | <code>        throw std::runtime_error(&quot;Invalid guidance_mode &#x27;&quot; + guidance_mode_ +</code> | Nếu không khớp ba chế độ, ném runtime_error kèm giá trị cấu hình sai... |
| 109 | <code>                                 &quot;&#x27;; expected none, corridor, or region_prior&quot;);</code> | ...và liệt kê các chế độ hợp lệ; không âm thầm fallback. |
| 110 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 111 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 112 | <code>    template &lt;typename Regions&gt;</code> | Hàm template dùng được với cả vector vùng thường và vector vùng có score. |
| 113 | <code>    void visualizeRegionBoundaries(const Regions &amp;regions,</code> | Nhận danh sách vùng bằng tham chiếu const, dùng chung thuộc tính polygon. |
| 114 | <code>                                   double z,</code> | z là độ cao mặt phẳng dùng để vẽ polygon 2D trong RViz 3D. |
| 115 | <code>                                   visualization::Color color)</code> | color là màu đường biên. |
| 116 | <code>    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 117 | <code>        std::vector&lt;std::pair&lt;Eigen::Vector3d, Eigen::Vector3d&gt;&gt; boundaries;</code> | Danh sách đoạn thẳng 3D, mỗi phần tử là pair hai vector đầu–cuối. |
| 118 | <code>        for (const auto &amp;region : regions)</code> | Duyệt từng vùng. |
| 119 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 120 | <code>            for (std::size_t i = 0; i &lt; region.polygon.size(); ++i)</code> | Duyệt chỉ số của mọi đỉnh polygon. |
| 121 | <code>            {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 122 | <code>                const Eigen::Vector2d &amp;a = region.polygon[i];</code> | Tham chiếu đỉnh đầu a của cạnh hiện tại, không sao chép. |
| 123 | <code>                const Eigen::Vector2d &amp;b = region.polygon[(i + 1) % region.polygon.size()];</code> | Lấy đỉnh kế tiếp b; modulo đóng vòng từ đỉnh cuối về đầu. |
| 124 | <code>                boundaries.emplace_back(Eigen::Vector3d(a.x(), a.y(), z),</code> | Tạo đầu a ở 3D bằng cách thêm z và bắt đầu emplace_back một cặp... |
| 125 | <code>                                        Eigen::Vector3d(b.x(), b.y(), z));</code> | ...với đầu b ở cùng z; emplace_back xây phần tử trực tiếp trong vector. |
| 126 | <code>            }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 127 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 128 | <code>        vis_ptr_-&gt;visualize_pairline(boundaries, &quot;guidance_regions&quot;, color, 0.08);</code> | Publish các đoạn biên dưới tên guidance_regions, độ rộng nét 0.08. |
| 129 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 130 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 131 | <code>    void visualizeGuidanceRegions(double z)</code> | Chọn bộ vùng và màu để vẽ theo mode. |
| 132 | <code>    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 133 | <code>        if (guidance_mode_ == &quot;corridor&quot;)</code> | Nếu corridor... |
| 134 | <code>            visualizeRegionBoundaries(corridor_.regions, z, visualization::orange);</code> | ...vẽ vùng route màu cam. |
| 135 | <code>        else if (guidance_mode_ == &quot;region_prior&quot;)</code> | Nếu region_prior... |
| 136 | <code>            visualizeRegionBoundaries(sampling_prior_.regions, z, visualization::yellow);</code> | ...vẽ tất cả vùng prior màu vàng; không đổi màu theo score ở đây. |
| 137 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 138 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 139 | <code>public:</code> | Các phương thức dưới đây là public, bên ngoài lớp có thể gọi. |
| 140 | <code>    TesterPathFinder(const ros::NodeHandle &amp;nh) : nh_(nh)</code> | Constructor nhận NodeHandle bằng const reference; initializer list nh_(nh) khởi tạo thành viên trước thân hàm. |
| 141 | <code>    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 142 | <code>        env_ptr_ = std::make_shared&lt;env::OccMap&gt;();</code> | make_shared tạo occupancy map trên heap và trả smart pointer quản lý vòng đời. |
| 143 | <code>        env_ptr_-&gt;init(nh_);</code> | Khởi tạo occupancy map với params/subscribers từ NodeHandle. |
| 144 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 145 | <code>        vis_ptr_ = std::make_shared&lt;visualization::Visualization&gt;(nh_);</code> | Tạo đối tượng visualization dùng chung. |
| 146 | <code>        vis_ptr_-&gt;registe&lt;visualization_msgs::Marker&gt;(&quot;start&quot;);</code> | Đăng ký kênh Marker có tên start để vẽ điểm bắt đầu. |
| 147 | <code>        vis_ptr_-&gt;registe&lt;visualization_msgs::Marker&gt;(&quot;goal&quot;);</code> | Đăng ký kênh Marker có tên goal để vẽ điểm đích. |
| 148 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 149 | <code>        rrt_sharp_ptr_ = std::make_shared&lt;path_plan::RRTSharp&gt;(nh_, env_ptr_);</code> | Tạo planner RRT#, truyền NodeHandle và cùng occupancy map. |
| 150 | <code>        rrt_sharp_ptr_-&gt;setVisualizer(vis_ptr_);</code> | Gắn visualization dùng chung vào planner RRT#. |
| 151 | <code>        vis_ptr_-&gt;registe&lt;nav_msgs::Path&gt;(&quot;rrt_sharp_final_path&quot;);</code> | Đăng ký kênh nav_msgs::Path để hiển thị đường cuối của RRT#. |
| 152 | <code>        vis_ptr_-&gt;registe&lt;sensor_msgs::PointCloud2&gt;(&quot;rrt_sharp_final_wpts&quot;);</code> | Đăng ký PointCloud2 để hiển thị waypoint của RRT#. |
| 153 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 154 | <code>        rrt_star_ptr_ = std::make_shared&lt;path_plan::RRTStar&gt;(nh_, env_ptr_);</code> | Tạo planner RRT*, truyền NodeHandle và cùng occupancy map. |
| 155 | <code>        rrt_star_ptr_-&gt;setVisualizer(vis_ptr_);</code> | Gắn visualization dùng chung vào planner RRT*. |
| 156 | <code>        vis_ptr_-&gt;registe&lt;nav_msgs::Path&gt;(&quot;rrt_star_final_path&quot;);</code> | Đăng ký kênh nav_msgs::Path để hiển thị đường cuối của RRT*. |
| 157 | <code>        vis_ptr_-&gt;registe&lt;sensor_msgs::PointCloud2&gt;(&quot;rrt_star_final_wpts&quot;);</code> | Đăng ký PointCloud2 để hiển thị waypoint của RRT*. |
| 158 | <code>        vis_ptr_-&gt;registe&lt;visualization_msgs::MarkerArray&gt;(&quot;rrt_star_paths&quot;);</code> | Đăng ký riêng MarkerArray để hiển thị nhiều nghiệm của RRT*. |
| 159 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 160 | <code>        rrt_ptr_ = std::make_shared&lt;path_plan::RRT&gt;(nh_, env_ptr_);</code> | Tạo planner RRT, truyền NodeHandle và cùng occupancy map. |
| 161 | <code>        rrt_ptr_-&gt;setVisualizer(vis_ptr_);</code> | Gắn visualization dùng chung vào planner RRT. |
| 162 | <code>        vis_ptr_-&gt;registe&lt;nav_msgs::Path&gt;(&quot;rrt_final_path&quot;);</code> | Đăng ký kênh nav_msgs::Path để hiển thị đường cuối của RRT. |
| 163 | <code>        vis_ptr_-&gt;registe&lt;sensor_msgs::PointCloud2&gt;(&quot;rrt_final_wpts&quot;);</code> | Đăng ký PointCloud2 để hiển thị waypoint của RRT. |
| 164 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 165 | <code>        brrt_ptr_ = std::make_shared&lt;path_plan::BRRT&gt;(nh_, env_ptr_);</code> | Tạo planner BRRT, truyền NodeHandle và cùng occupancy map. |
| 166 | <code>        brrt_ptr_-&gt;setVisualizer(vis_ptr_);</code> | Gắn visualization dùng chung vào planner BRRT. |
| 167 | <code>        vis_ptr_-&gt;registe&lt;nav_msgs::Path&gt;(&quot;brrt_final_path&quot;);</code> | Đăng ký kênh nav_msgs::Path để hiển thị đường cuối của BRRT. |
| 168 | <code>        vis_ptr_-&gt;registe&lt;sensor_msgs::PointCloud2&gt;(&quot;brrt_final_wpts&quot;);</code> | Đăng ký PointCloud2 để hiển thị waypoint của BRRT. |
| 169 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 170 | <code>        brrt_star_ptr_ = std::make_shared&lt;path_plan::BRRTStar&gt;(nh_, env_ptr_);</code> | Tạo planner BRRT*, truyền NodeHandle và cùng occupancy map. |
| 171 | <code>        brrt_star_ptr_-&gt;setVisualizer(vis_ptr_);</code> | Gắn visualization dùng chung vào planner BRRT*. |
| 172 | <code>        vis_ptr_-&gt;registe&lt;nav_msgs::Path&gt;(&quot;brrt_star_final_path&quot;);</code> | Đăng ký kênh nav_msgs::Path để hiển thị đường cuối của BRRT*. |
| 173 | <code>        vis_ptr_-&gt;registe&lt;sensor_msgs::PointCloud2&gt;(&quot;brrt_star_final_wpts&quot;);</code> | Đăng ký PointCloud2 để hiển thị waypoint của BRRT*. |
| 174 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 175 | <code>        goal_sub_ = nh_.subscribe(&quot;/goal&quot;, 1, &amp;TesterPathFinder::goalCallback, this);</code> | Subscribe topic tuyệt đối /goal, queue size 1; callback là phương thức goalCallback của đối tượng this. |
| 176 | <code>        execution_timer_ = nh_.createTimer(ros::Duration(1), &amp;TesterPathFinder::executionCallback, this);</code> | Tạo timer chu kỳ 1 giây, gọi executionCallback; không phải chạy planner mỗi giây. |
| 177 | <code>        rcv_glb_obs_client_ = nh_.serviceClient&lt;self_msgs_and_srvs::GlbObsRcv&gt;(&quot;/pub_glb_obs&quot;);</code> | Tạo client của service tuyệt đối /pub_glb_obs. |
| 178 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 179 | <code>        nh_.param(&quot;initial_start_x&quot;, start_[0], 0.0);</code> | Đọc tọa độ start x ban đầu; thiếu param thì 0.0. |
| 180 | <code>        nh_.param(&quot;initial_start_y&quot;, start_[1], 0.0);</code> | Đọc tọa độ start y ban đầu; thiếu param thì 0.0. |
| 181 | <code>        nh_.param(&quot;initial_start_z&quot;, start_[2], 0.0);</code> | Đọc tọa độ start z ban đầu; thiếu param thì 0.0. |
| 182 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 183 | <code>        nh_.param(&quot;run_rrt&quot;, run_rrt_, true);</code> | Đọc cờ run_rrt, mặc định true nếu không có param. |
| 184 | <code>        nh_.param(&quot;run_rrt_star&quot;, run_rrt_star_, true);</code> | Đọc cờ run_rrt_star, mặc định true. |
| 185 | <code>        nh_.param(&quot;run_rrt_sharp&quot;, run_rrt_sharp_, true);</code> | Đọc cờ run_rrt_sharp, mặc định true. |
| 186 | <code>        nh_.param(&quot;run_brrt&quot;, run_brrt_, false);</code> | Đọc cờ run_brrt, mặc định false; launch hiện tại truyền true nên ghi đè mặc định này. |
| 187 | <code>        nh_.param(&quot;run_brrt_star&quot;, run_brrt_star_, false);</code> | Đọc cờ run_brrt_star, mặc định false; launch hiện tại truyền true. |
| 188 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 189 | <code>        configureGuidance();</code> | Cấu hình guidance sau khi tất cả smart pointer planner đã được tạo, tránh truy cập pointer chưa khởi tạo. |
| 190 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 191 | <code>    ~TesterPathFinder(){};</code> | Destructor có thân rỗng; các thành viên smart pointer vẫn được hủy theo cơ chế C++. |
| 192 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 193 | <code>    void goalCallback(const geometry_msgs::PoseStamped::ConstPtr &amp;goal_msg)</code> | Callback nhận con trỏ const tới PoseStamped, truyền bằng const reference. |
| 194 | <code>    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 195 | <code>        goal_[0] = goal_msg-&gt;pose.position.x;</code> | Copy tọa độ x của message vào goal_. |
| 196 | <code>        goal_[1] = goal_msg-&gt;pose.position.y;</code> | Copy tọa độ y của message vào goal_. |
| 197 | <code>        goal_[2] = goal_msg-&gt;pose.position.z;</code> | Copy tọa độ z của message vào goal_; orientation và header.frame_id không được xử lý ở đây. |
| 198 | <code>        ROS_INFO_STREAM(&quot;\n-----------------------------\ngoal rcved at &quot; &lt;&lt; goal_.transpose());</code> | Log goal dạng vector hàng bằng transpose() cho dễ đọc. |
| 199 | <code>        visualizeGuidanceRegions(start_.z());</code> | Vẽ các vùng guidance tại z của start hiện tại. |
| 200 | <code>        vis_ptr_-&gt;visualize_a_ball(start_, 0.3, &quot;start&quot;, visualization::Color::pink);</code> | Vẽ quả cầu start màu hồng với tham số kích thước 0.3 của hàm visualization. |
| 201 | <code>        vis_ptr_-&gt;visualize_a_ball(goal_, 0.3, &quot;goal&quot;, visualization::Color::steelblue);</code> | Vẽ quả cầu goal màu steelblue với cùng tham số 0.3. |
| 202 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 203 | <code>        // BiasSampler sampler;</code> | Code comment, không chạy: ý tưởng tạo một sampler riêng để sinh bộ mẫu dùng lại. |
| 204 | <code>        // sampler.setSamplingRange(env_ptr_-&gt;getOrigin(), env_ptr_-&gt;getMapSize());</code> | Code comment, không chạy: thiết lập khung lấy mẫu theo origin và kích thước map. |
| 205 | <code>        // vector&lt;Eigen::Vector3d&gt; preserved_samples;</code> | Code comment, không chạy: danh sách lưu các điểm mẫu. |
| 206 | <code>        // for (int i = 0; i &lt; 5000; ++i)</code> | Code comment, không chạy: vòng lặp dự định tạo 5000 mẫu. |
| 207 | <code>        // {</code> | Comment chứa dấu mở khối của vòng lặp đã bị vô hiệu hóa. |
| 208 | <code>        //     Eigen::Vector3d rand_sample;</code> | Code comment, không chạy: biến điểm mẫu 3D. |
| 209 | <code>        //     sampler.uniformSamplingOnce(rand_sample);</code> | Code comment, không chạy: lấy một mẫu uniform. |
| 210 | <code>        //     preserved_samples.push_back(rand_sample);</code> | Code comment, không chạy: thêm mẫu vào bộ dùng chung. |
| 211 | <code>        // }</code> | Comment chứa dấu đóng khối vòng lặp đã bị vô hiệu hóa. |
| 212 | <code>        // rrt_ptr_-&gt;setPreserveSamples(preserved_samples);</code> | Code comment, không chạy: cấp cùng bộ mẫu cho RRT. |
| 213 | <code>        // rrt_star_ptr_-&gt;setPreserveSamples(preserved_samples);</code> | Code comment, không chạy: cấp cùng bộ mẫu cho RRT*. |
| 214 | <code>        // rrt_sharp_ptr_-&gt;setPreserveSamples(preserved_samples);</code> | Code comment, không chạy: cấp cùng bộ mẫu cho RRT#; hiện các planner không chia sẻ bộ mẫu theo block này. |
| 215 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 216 | <code>        if (run_rrt_)</code> | Chỉ chạy RRT nếu cờ tương ứng bật. Các block planner chạy tuần tự trong cùng goalCallback. |
| 217 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 218 | <code>            bool rrt_res = rrt_ptr_-&gt;plan(start_, goal_);</code> | Gọi plan(start_,goal_) của RRT; thuật toán và kiểm tra va chạm ở header planner, kết quả bool báo thành công. |
| 219 | <code>            if (rrt_res)</code> | Chỉ lấy và hiển thị đường khi RRT trả true. |
| 220 | <code>            {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 221 | <code>                vector&lt;Eigen::Vector3d&gt; final_path = rrt_ptr_-&gt;getPath();</code> | Lấy đường cuối RRT dưới dạng vector các waypoint Eigen::Vector3d. |
| 222 | <code>                vis_ptr_-&gt;visualize_path(final_path, &quot;rrt_final_path&quot;);</code> | Publish đường RRT để RViz nối các waypoint. |
| 223 | <code>                vis_ptr_-&gt;visualize_pointcloud(final_path, &quot;rrt_final_wpts&quot;);</code> | Publish cùng waypoint dưới dạng point cloud cho RRT. |
| 224 | <code>                vector&lt;std::pair&lt;double, double&gt;&gt; slns = rrt_ptr_-&gt;getSolutions();</code> | Lấy lịch sử nghiệm RRT, mỗi pair lưu cost và thời gian tìm thấy nghiệm. |
| 225 | <code>                ROS_INFO_STREAM(&quot;[RRT] final path len: &quot; &lt;&lt; slns.back().first);</code> | In cost của nghiệm cuối RRT: back() lấy phần tử cuối, first lấy cost. Code giả định list không rỗng sau khi plan thành công; đây không phải cost LLM. |
| 226 | <code>            }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 227 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 228 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 229 | <code>        if (run_rrt_star_)</code> | Chỉ chạy RRT* nếu cờ tương ứng bật. Các block planner chạy tuần tự trong cùng goalCallback. |
| 230 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 231 | <code>            bool rrt_star_res = rrt_star_ptr_-&gt;plan(start_, goal_);</code> | Gọi plan(start_,goal_) của RRT*; thuật toán và kiểm tra va chạm ở header planner, kết quả bool báo thành công. |
| 232 | <code>            if (rrt_star_res)</code> | Chỉ lấy và hiển thị đường khi RRT* trả true. |
| 233 | <code>            {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 234 | <code>                vector&lt;vector&lt;Eigen::Vector3d&gt;&gt; routes = rrt_star_ptr_-&gt;getAllPaths();</code> | Riêng RRT*: lấy danh sách các đường nghiệm đã ghi trong quá trình cải thiện. |
| 235 | <code>                vis_ptr_-&gt;visualize_path_list(routes, &quot;rrt_star_paths&quot;, visualization::blue);</code> | Vẽ danh sách đường RRT* màu xanh. |
| 236 | <code>                vector&lt;Eigen::Vector3d&gt; final_path = rrt_star_ptr_-&gt;getPath();</code> | Lấy đường cuối RRT* dưới dạng vector các waypoint Eigen::Vector3d. |
| 237 | <code>                vis_ptr_-&gt;visualize_path(final_path, &quot;rrt_star_final_path&quot;);</code> | Publish đường RRT* để RViz nối các waypoint. |
| 238 | <code>                vis_ptr_-&gt;visualize_pointcloud(final_path, &quot;rrt_star_final_wpts&quot;);</code> | Publish cùng waypoint dưới dạng point cloud cho RRT*. |
| 239 | <code>                vector&lt;std::pair&lt;double, double&gt;&gt; slns = rrt_star_ptr_-&gt;getSolutions();</code> | Lấy lịch sử nghiệm RRT*, mỗi pair lưu cost và thời gian tìm thấy nghiệm. |
| 240 | <code>                ROS_INFO_STREAM(&quot;[RRT*] final path len: &quot; &lt;&lt; slns.back().first);</code> | In cost của nghiệm cuối RRT*: back() lấy phần tử cuối, first lấy cost. Code giả định list không rỗng sau khi plan thành công; đây không phải cost LLM. |
| 241 | <code>            }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 242 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 243 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 244 | <code>        if (run_rrt_sharp_)</code> | Chỉ chạy RRT# nếu cờ tương ứng bật. Các block planner chạy tuần tự trong cùng goalCallback. |
| 245 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 246 | <code>            bool rrt_sharp_res = rrt_sharp_ptr_-&gt;plan(start_, goal_);</code> | Gọi plan(start_,goal_) của RRT#; thuật toán và kiểm tra va chạm ở header planner, kết quả bool báo thành công. |
| 247 | <code>            if (rrt_sharp_res)</code> | Chỉ lấy và hiển thị đường khi RRT# trả true. |
| 248 | <code>            {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 249 | <code>                vector&lt;Eigen::Vector3d&gt; final_path = rrt_sharp_ptr_-&gt;getPath();</code> | Lấy đường cuối RRT# dưới dạng vector các waypoint Eigen::Vector3d. |
| 250 | <code>                vis_ptr_-&gt;visualize_path(final_path, &quot;rrt_sharp_final_path&quot;);</code> | Publish đường RRT# để RViz nối các waypoint. |
| 251 | <code>                vis_ptr_-&gt;visualize_pointcloud(final_path, &quot;rrt_sharp_final_wpts&quot;);</code> | Publish cùng waypoint dưới dạng point cloud cho RRT#. |
| 252 | <code>                vector&lt;std::pair&lt;double, double&gt;&gt; slns = rrt_sharp_ptr_-&gt;getSolutions();</code> | Lấy lịch sử nghiệm RRT#, mỗi pair lưu cost và thời gian tìm thấy nghiệm. |
| 253 | <code>                ROS_INFO_STREAM(&quot;[RRT#] final path len: &quot; &lt;&lt; slns.back().first);</code> | In cost của nghiệm cuối RRT#: back() lấy phần tử cuối, first lấy cost. Code giả định list không rỗng sau khi plan thành công; đây không phải cost LLM. |
| 254 | <code>            }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 255 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 256 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 257 | <code>        if (run_brrt_)</code> | Chỉ chạy BRRT nếu cờ tương ứng bật. Các block planner chạy tuần tự trong cùng goalCallback. |
| 258 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 259 | <code>            bool brrt_res = brrt_ptr_-&gt;plan(start_, goal_);</code> | Gọi plan(start_,goal_) của BRRT; thuật toán và kiểm tra va chạm ở header planner, kết quả bool báo thành công. |
| 260 | <code>            if (brrt_res)</code> | Chỉ lấy và hiển thị đường khi BRRT trả true. |
| 261 | <code>            {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 262 | <code>                vector&lt;Eigen::Vector3d&gt; final_path = brrt_ptr_-&gt;getPath();</code> | Lấy đường cuối BRRT dưới dạng vector các waypoint Eigen::Vector3d. |
| 263 | <code>                vis_ptr_-&gt;visualize_path(final_path, &quot;brrt_final_path&quot;);</code> | Publish đường BRRT để RViz nối các waypoint. |
| 264 | <code>                vis_ptr_-&gt;visualize_pointcloud(final_path, &quot;brrt_final_wpts&quot;);</code> | Publish cùng waypoint dưới dạng point cloud cho BRRT. |
| 265 | <code>                vector&lt;std::pair&lt;double, double&gt;&gt; slns = brrt_ptr_-&gt;getSolutions();</code> | Lấy lịch sử nghiệm BRRT, mỗi pair lưu cost và thời gian tìm thấy nghiệm. |
| 266 | <code>                ROS_INFO_STREAM(&quot;[BRRT] final path len: &quot; &lt;&lt; slns.back().first);</code> | In cost của nghiệm cuối BRRT: back() lấy phần tử cuối, first lấy cost. Code giả định list không rỗng sau khi plan thành công; đây không phải cost LLM. |
| 267 | <code>            }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 268 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 269 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 270 | <code>        if (run_brrt_star_)</code> | Chỉ chạy BRRT* nếu cờ tương ứng bật. Các block planner chạy tuần tự trong cùng goalCallback. |
| 271 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 272 | <code>            bool brrt_star_res = brrt_star_ptr_-&gt;plan(start_, goal_);</code> | Gọi plan(start_,goal_) của BRRT*; thuật toán và kiểm tra va chạm ở header planner, kết quả bool báo thành công. |
| 273 | <code>            if (brrt_star_res)</code> | Chỉ lấy và hiển thị đường khi BRRT* trả true. |
| 274 | <code>            {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 275 | <code>                vector&lt;Eigen::Vector3d&gt; final_path = brrt_star_ptr_-&gt;getPath();</code> | Lấy đường cuối BRRT* dưới dạng vector các waypoint Eigen::Vector3d. |
| 276 | <code>                vis_ptr_-&gt;visualize_path(final_path, &quot;brrt_star_final_path&quot;);</code> | Publish đường BRRT* để RViz nối các waypoint. |
| 277 | <code>                vis_ptr_-&gt;visualize_pointcloud(final_path, &quot;brrt_star_final_wpts&quot;);</code> | Publish cùng waypoint dưới dạng point cloud cho BRRT*. |
| 278 | <code>                vector&lt;std::pair&lt;double, double&gt;&gt; slns = brrt_star_ptr_-&gt;getSolutions();</code> | Lấy lịch sử nghiệm BRRT*, mỗi pair lưu cost và thời gian tìm thấy nghiệm. |
| 279 | <code>                ROS_INFO_STREAM(&quot;[BRRT*] final path len: &quot; &lt;&lt; slns.back().first);</code> | In cost của nghiệm cuối BRRT*: back() lấy phần tử cuối, first lấy cost. Code giả định list không rỗng sau khi plan thành công; đây không phải cost LLM. |
| 280 | <code>            }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 281 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 282 | <code>        </code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 283 | <code>        start_ = goal_;</code> | Gán goal thành start cho lần click tiếp theo, kể cả khi mọi planner vừa thất bại. Đây chỉ là trạng thái demo, không phải robot đã di chuyển thật. |
| 284 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 285 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 286 | <code>    void executionCallback(const ros::TimerEvent &amp;event)</code> | Callback timer; event được nhận theo chữ ký ROS nhưng không dùng trong thân hàm. |
| 287 | <code>    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 288 | <code>        if (!env_ptr_-&gt;mapValid())</code> | Nếu occupancy map chưa báo hợp lệ... |
| 289 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 290 | <code>            ROS_INFO(&quot;no map rcved yet.&quot;);</code> | ...log chưa nhận được map. |
| 291 | <code>            self_msgs_and_srvs::GlbObsRcv srv;</code> | Tạo object request/response cho service GlbObsRcv. |
| 292 | <code>            if (!rcv_glb_obs_client_.call(srv))</code> | Gọi service đồng bộ để yêu cầu nguồn map publish; ! là nếu gọi thất bại. |
| 293 | <code>                ROS_WARN(&quot;Failed to call service /pub_glb_obs&quot;);</code> | Log warning khi service call thất bại. |
| 294 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 295 | <code>        else</code> | Nhánh map đã hợp lệ. |
| 296 | <code>        {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 297 | <code>            execution_timer_.stop();</code> | Dừng timer kiểm tra map, không dừng subscribers hay spinner. |
| 298 | <code>        }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 299 | <code>    };</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 300 | <code>};</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 301 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 302 | <code>int main(int argc, char **argv)</code> | Entry point C++, argc là số đối số và argv là mảng chuỗi đối số. |
| 303 | <code>{</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 304 | <code>    ros::init(argc, argv, &quot;test_path_finder_node&quot;);</code> | Khởi tạo ROS với tên mặc định test_path_finder_node; roslaunch có thể remap tên node. |
| 305 | <code>    ros::NodeHandle nh(&quot;~&quot;);</code> | Tạo private NodeHandle (~), nên params được tra trong namespace riêng của node. |
| 306 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 307 | <code>    try</code> | Bắt exception đồng bộ phát sinh trong phạm vi main bên dưới. |
| 308 | <code>    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 309 | <code>        TesterPathFinder tester(nh);</code> | Tạo TesterPathFinder, chạy constructor khởi tạo map, planner, callbacks và guidance. |
| 310 | <code>&nbsp;</code> | Dòng trống để tách các nhóm code; không có lệnh thực thi. |
| 311 | <code>        ros::AsyncSpinner spinner(0);</code> | AsyncSpinner(0): ROS chọn số worker theo số lõi phần cứng; không có nghĩa là chạy năm planner song song trong callback. |
| 312 | <code>        spinner.start();</code> | Khởi động các thread xử lý ROS callbacks. |
| 313 | <code>        ros::waitForShutdown();</code> | Chờ ROS shutdown, giữ tester và spinner còn sống. |
| 314 | <code>        return 0;</code> | Kết thúc bình thường với mã 0. |
| 315 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 316 | <code>    catch (const std::exception &amp;error)</code> | Bắt std::exception từ khối try; không nên coi đây là cơ chế bắt mọi lỗi trong callback ở worker thread khác. |
| 317 | <code>    {</code> | Mở biểu thức/khối đã bắt đầu ở dòng trước; không tạo thao tác độc lập. |
| 318 | <code>        ROS_FATAL_STREAM(&quot;Failed to initialize path planner: &quot; &lt;&lt; error.what());</code> | Log lỗi nghiêm trọng, dùng what() lấy nội dung exception. |
| 319 | <code>        return 1;</code> | Trả mã lỗi 1 khi khởi tạo/phần đồng bộ main thất bại. |
| 320 | <code>    }</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
| 321 | <code>}</code> | Đóng biểu thức, cấu trúc dữ liệu hoặc khối đang mở; xem các dòng phía trên để hiểu thao tác đầy đủ. |
