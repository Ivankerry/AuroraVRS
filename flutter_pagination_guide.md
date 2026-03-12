# 🔄 Flutter Infinite Scroll & Pagination Guide

This guide provides a detailed implementation of infinite scrolling for the AuroraVRS video feed.

## 🚀 Overview
To ensure a smooth user experience, the app should fetch videos in batches of 20 and automatically load more as the user reaches the end of the current list.

### Key Components:
- **`ScrollController`**: Detects scroll position.
- **`Dio`**: Handles HTTP requests with `page` and `limit` parameters.
- **`has_more`**: A boolean from the server indicating if more content exists.

---

## 🛠️ Implementation Example

```dart
import 'package:flutter/material.dart';
import 'package:dio/dio.dart';

class VideoFeedScreen extends StatefulWidget {
  @override
  _VideoFeedScreenState createState() => _VideoFeedScreenState();
}

class _VideoFeedScreenState extends State<VideoFeedScreen> {
  final ScrollController _scrollController = ScrollController();
  final Dio dio = Dio(BaseOptions(baseUrl: "http://62.84.176.140:8080"));
  
  List _videos = [];
  int _currentPage = 1;
  bool _isFetching = false;
  bool _hasMore = true;

  @override
  void initState() {
    super.initState();
    _fetchNextBatch();
    
    // Listen to scroll events
    _scrollController.addListener(() {
      // Trigger fetch when user is 200px from the bottom
      if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
        _fetchNextBatch();
      }
    });
  }

  Future<void> _fetchNextBatch() async {
    // Prevent duplicate calls or fetching when no more data
    if (_isFetching || !_hasMore) return;

    setState(() => _isFetching = true);

    try {
      final response = await dio.get("/api/v1/feed", queryParameters: {
        "video_type": "QUICK",
        "page": _currentPage,
        "limit": 20, // Standard batch size
      });

      final List newVideos = response.data['videos'];
      final bool moreAvailable = response.data['has_more'];

      setState(() {
        _videos.addAll(newVideos);
        _currentPage++;
        _hasMore = moreAvailable;
        _isFetching = false;
      });
    } catch (e) {
      setState(() => _isFetching = false);
      debugPrint("❌ Error fetching feed: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async {
        // Reset state for "Pull to Refresh"
        setState(() {
          _videos = [];
          _currentPage = 1;
          _hasMore = true;
        });
        await _fetchNextBatch();
      },
      child: ListView.builder(
        controller: _scrollController,
        itemCount: _videos.length + (_hasMore ? 1 : 0),
        itemBuilder: (context, index) {
          // Show loading spinner at the bottom
          if (index == _videos.length) {
            return const Padding(
              padding: EdgeInsets.all(16.0),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          
          final video = _videos[index];
          return ListTile(
            title: Text(video['title']),
            subtitle: Text("Tags: ${video['tags'].join(', ')}"),
          );
        },
      ),
    );
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }
}
```

---

## 💡 Best Practices
1.  **Deduplication**: The backend handles deduplication automatically for logged-in users.
2.  **Pull to Refresh**: Use `RefreshIndicator` to allow users to reset the feed.
3.  **Loading States**: Always show a `CircularProgressIndicator` at the end of the list if `has_more` is true.
