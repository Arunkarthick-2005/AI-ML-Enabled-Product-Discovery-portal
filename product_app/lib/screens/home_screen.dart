import 'package:flutter/material.dart';
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
  HomeViewState? _lastViewState;

  Future<List<Product>>? _searchFuture;
  Future<HomeCollections>? _homeFuture;
  Future<List<Product>>? _recentFuture;

  final List<String> _productHistory = [];
  String? _lastQuery;

  @override
  void initState() {
    super.initState();
    _homeFuture = ProductService.fetchHomeCollections();
    _recentFuture =
        RecommendationService.getUserRecommendations(widget.userId);
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
  // OPEN PRODUCT (✅ FINAL)
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
  // --------------------------------------------------
  // BACK HANDLING
  // --------------------------------------------------
void _handleBack() {
  setState(() {
    _lastViewState = _viewState;

    if (_viewState == HomeViewState.detail) {
      _productHistory.removeLast();

      if (_productHistory.isEmpty) {
        _viewState = _previousViewState ?? HomeViewState.home;

        // ✅ REFRESH RECOMMENDATIONS WHEN BACK TO HOME
        if (_viewState == HomeViewState.home) {
          _recentFuture =
              RecommendationService.getUserRecommendations(widget.userId);
        }
      }
      return;
    }

    if (_viewState == HomeViewState.results) {
      _viewState = HomeViewState.home;

      _searchFuture = null;
      _lastQuery = null;

      // ✅ REFRESH RECOMMENDATIONS
      _recentFuture =
          RecommendationService.getUserRecommendations(widget.userId);
    }
  });
}

  // --------------------------------------------------
  // LOGOUT
  // --------------------------------------------------
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
      body: Column(
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
    );
  }

  // --------------------------------------------------
  // HEADER
  // --------------------------------------------------
  Widget _buildHeader() {
    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      color: Colors.blue,
      child: Row(
        children: [
          if (_viewState != HomeViewState.home)
            IconButton(
              icon: const Icon(Icons.arrow_back, color: Colors.white),
              onPressed: _handleBack,
            ),
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
        return _buildHomeCollections();

      case HomeViewState.results:
        return _buildSearchResults();

      case HomeViewState.detail:
        return ProductDetailView(
          productId: _productHistory.last,
          onOpenProduct: _openProduct,
        );
    }
  }

  // --------------------------------------------------
  // HOME COLLECTIONS + RECENT
  // --------------------------------------------------
  Widget _buildHomeCollections() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _buildRecentlySearchedSection(),
          const SizedBox(height: 24),
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
                  _buildSection("Furniture", data.forFurniture),
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
  // SEARCH RESULTS (✅ search_view)
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
            crossAxisCount: 7,
            crossAxisSpacing: 16,
            mainAxisSpacing: 16,
            childAspectRatio: 0.70,
          ),
          itemBuilder: (_, i) => InkWell(
            onTap: () => _openProduct(
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
  // RECENTLY SEARCHED (✅ view)
  // --------------------------------------------------
  Widget _buildRecentlySearchedSection() {
    return FutureBuilder<List<Product>>(
      future: _recentFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const SizedBox.shrink();
        }
        return _buildSection("Recently Searched", snapshot.data!);
      },
    );
  }

  // --------------------------------------------------
  // SECTION BUILDER (✅ view)
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
            itemBuilder: (_, index) => InkWell(
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
  // PRODUCT CARD (UI‑ONLY)
  // --------------------------------------------------
  Widget _buildProductCard(Product product) {
  final sellingPrice = product.price?['selling'];
  final imageUrl = product.images.isNotEmpty
      ? "http://localhost:8000/image-proxy?url=${Uri.encodeComponent(product.images.first)}"
      : null;

  return Material(
    color: Colors.white,
    borderRadius: BorderRadius.circular(16),
    elevation: 1.5,
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 110,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: imageUrl != null
                  ? Image.network(imageUrl, fit: BoxFit.contain)
                  : const Icon(Icons.image),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            product.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
          Text(
            product.brand ?? "",
            style:
                TextStyle(fontSize: 12, color: Colors.grey.shade700),
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              if (sellingPrice != null)
                Text(
                  "₹$sellingPrice",
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              InkWell(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          CopilotChatView(productId: product.pid),
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