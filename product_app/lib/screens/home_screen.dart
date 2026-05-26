import 'package:flutter/material.dart';
import 'package:product_app/services/auth_service.dart';
import '../widgets/search_bar_widget.dart';
import '../models/product.dart';
import '../services/product_service.dart';
import '../services/recommendation_service.dart';
import 'product_detail_view.dart';
import 'login_screen.dart';
import 'copilot_chat_view.dart';

enum HomeViewState { home, results, detail }

class HomeScreen extends StatefulWidget {
  final String username;
  final String userId;
  const HomeScreen({super.key, required this.username, required this.userId});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  HomeViewState _viewState = HomeViewState.home;
  HomeViewState? _previousViewState;

  Future<List<Product>>? _searchFuture;
  Future<HomeCollections>? _homeFuture;
  Future<List<Product>>? _recentFuture;

  // ✅ NEW: Trending per category
  Future<Map<String, List<Product>>>? _trendingFuture;

  final List<String> _productHistory = [];
  String? _lastQuery;

  @override
  void initState() {
    super.initState();
    _homeFuture = ProductService.fetchHomeCollections();
    _recentFuture =
        RecommendationService.getUserRecommendations(widget.userId);

    // ✅ Load trending products
    _trendingFuture =
        RecommendationService.getTrendingByCategory(topNPerCategory: 3);
  }

  // --------------------------------------------------
  // SEARCH
  // --------------------------------------------------
  void _onSearch(String query) {
    setState(() {
      _lastQuery = query;
      _searchFuture = ProductService.searchProducts(query: query);
      _viewState = HomeViewState.results;
    });
  }

  // --------------------------------------------------
  // OPEN PRODUCT
  // --------------------------------------------------
  void _openProduct(
      String productId, {
        bool fromSearch = false,
        bool fromSimilar = false,
      }) {
    setState(() {
      if (_viewState != HomeViewState.detail) {
        _previousViewState = _viewState;
      }
      _productHistory.add(productId);
      _viewState = HomeViewState.detail;
    });

    if (fromSearch) {
      RecommendationService.logSearchView(
        userId: widget.userId,
        productId: productId,
      );
    } else if (fromSimilar) {
      RecommendationService.logInteraction(
        userId: widget.userId,
        productId: productId,
        eventType: "similar_view",
        source: "similar_products",
      );
    } else {
      RecommendationService.logView(
        userId: widget.userId,
        productId: productId,
      );
    }
  }

  void _showProfilePanel() {
    showGeneralDialog(
      context: context,
      barrierDismissible: true,
      barrierLabel: "Profile",
      transitionDuration: const Duration(milliseconds: 300),

      transitionBuilder: (context, animation, _, child) {
        return SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(-1, 0),
            end: Offset.zero,
          ).animate(animation),
          child: child,
        );
      },

      pageBuilder: (_, __, ___) {
        return SafeArea(
          child: Align(
            alignment: Alignment.topLeft, // ✅ FIX 1 (top-left)

            child: Material(
              color: Colors.transparent,

              child: FutureBuilder<Map<String, dynamic>?>(
                future: AuthService.getUserProfile(widget.userId),
                builder: (context, snapshot) {

                  if (!snapshot.hasData) {
                    return const SizedBox(
                      width: 260,
                      child: Center(child: CircularProgressIndicator()),
                    );
                  }

                  final user = snapshot.data!;

                  return Container(
                    width: 260,
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      // ✅ REMOVE full curve (feels floating)
                      borderRadius: BorderRadius.only(
                        topRight: Radius.circular(12),
                        bottomRight: Radius.circular(12),
                      ),
                    ),

                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [

                        // ✅ HEADER
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(16),
                          decoration: const BoxDecoration(
                            color: Colors.blue,
                            borderRadius: BorderRadius.only(
                              topRight: Radius.circular(12),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Icon(Icons.person,
                                  color: Colors.white, size: 32),
                              const SizedBox(height: 8),

                              Text(
                                user["name"] ?? "",
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 16,
                                ),
                              ),

                              Text(
                                user["email"] ?? "",
                                style: const TextStyle(color: Colors.white),
                              ),
                            ],
                          ),
                        ),

                        // ✅ PHONE
                        ListTile(
                          leading: const Icon(Icons.phone),
                          title: Text(user["mobile"] ?? ""),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ),
        );
      },
    );
  }

  // --------------------------------------------------
  // BACK HANDLING
  // --------------------------------------------------
  void _handleBack() {
    setState(() {
      if (_viewState == HomeViewState.detail) {
        _productHistory.removeLast();

        if (_productHistory.isEmpty) {
          _viewState = _previousViewState ?? HomeViewState.home;

          if (_viewState == HomeViewState.home) {
            // ✅ REFRESH BOTH
            _recentFuture =
                RecommendationService.getUserRecommendations(widget.userId);

            _trendingFuture =
                RecommendationService.getTrendingByCategory(
                  topNPerCategory: 3,
                );
          }
        }
        return;
      }

      if (_viewState == HomeViewState.results) {
        _viewState = HomeViewState.home;

        _searchFuture = null;
        _lastQuery = null;

        // ✅ REFRESH BOTH
        _recentFuture =
            RecommendationService.getUserRecommendations(widget.userId);

        _trendingFuture =
            RecommendationService.getTrendingByCategory(
              topNPerCategory: 3,
            );
      }
    });
  }

  void _logout(BuildContext context) {
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
          (_) => false,
    );
  }


  // --------------------------------------------------
  // UI
  // --------------------------------------------------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            if (_viewState != HomeViewState.detail)
              Padding(
                padding: const EdgeInsets.all(16),
                child: SearchBarWidget(onSearch: _onSearch),
              ),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }


  Widget _buildHeader() {
    return Container(
      height: 60,
      padding: const EdgeInsets.only(right: 16), // ✅ FIXED (no left gap)
      color: Colors.blue,
      child: Row(
        children: [

          // ✅ LEFT ICON (NO GAP)
          if (_viewState != HomeViewState.home)
            IconButton(
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(),
              icon: const Icon(Icons.arrow_back, color: Colors.white),
              onPressed: _handleBack,
            )
          else
            IconButton(
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(),
              icon: const Icon(Icons.person, color: Colors.white),
              onPressed: _showProfilePanel, // ✅ CORRECT
            ),



          const SizedBox(width: 10),

          // ✅ TITLE
          const Expanded(
            child: Text(
              "Product Discovery Portal",
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),

          // ✅ RIGHT ICON (still has spacing)
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white),
            onPressed: () => _logout(context),
          ),
        ],
      ),
    );
  }

  // --------------------------------------------------
  // BODY SWITCH
  // --------------------------------------------------
  Widget _buildBody() {
    switch (_viewState) {
      case HomeViewState.home:
        return _buildHome();
      case HomeViewState.results:
        return _buildSearchResults();
      case HomeViewState.detail:
        return ProductDetailView(
          productId: _productHistory.last,
          onOpenProduct: _openProduct,
          query: _lastQuery, // ✅ IMPORTANT
        );
    }
  }

  // --------------------------------------------------
  // HOME VIEW
  // --------------------------------------------------
  Widget _buildHome() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _buildRecentlySearchedSection(),
          const SizedBox(height: 24),

          // ✅ NEW: Trending in every category
          _buildTrendingCategories(),
          const SizedBox(height: 32),

          FutureBuilder<HomeCollections>(
            future: _homeFuture,
            builder: (context, snapshot) {
              if (!snapshot.hasData) {
                return const CircularProgressIndicator();
              }

              final data = snapshot.data!;
              return Column(
                children: [
                  _buildSection("Electronics", data.forElectronics),
                  _buildSection("Home & Living", data.forFurniture),
                  _buildSection("Clothing", data.forClothings),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  // --------------------------------------------------
// ✅ TRENDING PER CATEGORY UI
// --------------------------------------------------
  Widget _buildTrendingCategories() {
    return FutureBuilder<Map<String, List<Product>>>(
      future: _trendingFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const SizedBox.shrink();
        }

        final trendingMap = snapshot.data!;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: trendingMap.entries.map((entry) {
            return _buildSection(
              "Trending in ${entry.key}",
              entry.value,
            );
          }).toList(),
        );
      },
    );
  }

  // --------------------------------------------------
  // SEARCH RESULTS
  // --------------------------------------------------
  Widget _buildSearchResults() {
    return FutureBuilder<List<Product>>(
      future: _searchFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }

        final products = snapshot.data!;
        if (products.isEmpty) {
          return const Center(child: Text("No products found"));
        }

        return GridView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: products.length,
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2, // ✅ FIXED (2 per row)
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 0.85, // ✅ better mobile ratio
          ),
          itemBuilder: (_, i) =>
              InkWell(
                onTap: () =>
                    _openProduct(
                      products[i].pid,
                      fromSearch: true,
                    ),
                child: _buildProductCard(products[i]),
              ),
        );
      },
    );
  }

  // --------------------------------------------------
  // RECENTLY SEARCHED
  // --------------------------------------------------
  Widget _buildRecentlySearchedSection() {
    return FutureBuilder<List<Product>>(
      future: _recentFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const SizedBox.shrink();
        }
        return _buildSection("Recently Visited", snapshot.data!);
      },
    );
  }

  // --------------------------------------------------
  // SECTION BUILDER
  // --------------------------------------------------
  Widget _buildSection(String title, List<Product> products) {
    const double cardWidth = 180;
    const double cardHeight = cardWidth / 0.78;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style:
            const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
        const SizedBox(height: 12),
        SizedBox(
          height: cardHeight,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: products.length,
            separatorBuilder: (_, __) => const SizedBox(width: 16),
            itemBuilder: (_, index) =>
                InkWell(
                  onTap: () => _openProduct(products[index].pid),
                  child: SizedBox(
                    width: cardWidth,
                    child: _buildProductCard(products[index]),
                  ),
                ),
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }

  // --------------------------------------------------
  // PRODUCT CARD
  // --------------------------------------------------
  Widget _buildProductCard(Product product) {
    final sellingPrice = product.price?['selling'];

    final imageUrl = product.images.isNotEmpty
        ? "http://10.0.2.2:8000/image-proxy?url=${Uri.encodeComponent(
        product.images.first)}"
        : null;

    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(12),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(6), // ✅ reduced
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.max, // ✅ important
          children: [

            // ✅ FIXED IMAGE HEIGHT (prevents stretch)
            SizedBox(
              height: 110,
              width: double.infinity,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: imageUrl != null
                    ? Image.network(
                  imageUrl,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) =>
                  const Icon(Icons.broken_image),
                )
                    : const Icon(Icons.image),
              ),
            ),

            const SizedBox(height: 6),

            // ✅ TITLE
            Text(
              product.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),

            const SizedBox(height: 2),

            // ✅ BRAND
            Text(
              product.brand ?? "",
              style: TextStyle(
                fontSize: 10,
                color: Colors.grey.shade700,
              ),
            ),

            const SizedBox(height: 4),

            // ✅ PRICE + ICON
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [

                if (sellingPrice != null)
                  Text(
                    "₹$sellingPrice",
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                    ),
                  ),

                // ✅ ✅ COPILOT BUTTON (FIXED)
                GestureDetector(
                  behavior: HitTestBehavior.opaque, // ✅ important
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => CopilotChatView(
                          productId: product.pid,
                        ),
                      ),
                    );
                  },
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: Colors.blue,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Icon(
                      Icons.auto_awesome,
                      size: 14,
                      color: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
