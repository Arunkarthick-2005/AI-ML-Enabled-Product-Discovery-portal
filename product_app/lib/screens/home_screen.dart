import 'package:flutter/material.dart';
import '../widgets/search_bar_widget.dart';
import '../models/product.dart';
import '../services/product_service.dart';
import 'product_detail_view.dart';
import 'login_screen.dart';
import 'copilot_chat_view.dart';

enum HomeViewState { home, results, detail, copilotGeneric }

class HomeScreen extends StatefulWidget {
  final String username;

  const HomeScreen({
    super.key,
    required this.username,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  HomeViewState _viewState = HomeViewState.home;

  Future<List<Product>>? _searchFuture;
  final List<String> _productHistory = [];

  // --------------------------------------------------
  // SEARCH
  // --------------------------------------------------
  void _onSearch(String query) {
    setState(() {
      _searchFuture = ProductService.searchProducts(query: query);
      _viewState = HomeViewState.results;
    });
  }

  // --------------------------------------------------
  // PRODUCT DETAIL
  // --------------------------------------------------
  void _openProduct(String productId) {
    setState(() {
      _productHistory.add(productId);
      _viewState = HomeViewState.detail;
    });
  }

  // --------------------------------------------------
  // GENERIC COPILOT
  // --------------------------------------------------
  void _openGenericCopilot() {
    setState(() {
      _viewState = HomeViewState.copilotGeneric;
    });
  }

  // --------------------------------------------------
  // BACK HANDLING
  // --------------------------------------------------
  void _handleBack() {
    setState(() {
      if (_viewState == HomeViewState.copilotGeneric) {
        _viewState = HomeViewState.home;
        return;
      }

      if (_viewState == HomeViewState.detail) {
        if (_productHistory.length > 1) {
          _productHistory.removeLast();
        } else {
          _productHistory.clear();
          _viewState = HomeViewState.results;
        }
        return;
      }

      if (_viewState == HomeViewState.results) {
        _viewState = HomeViewState.home;
        _searchFuture = null;
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

      // ✅ GENERIC COPILOT (HOME ONLY)
      floatingActionButton:
          _viewState == HomeViewState.home
              ? FloatingActionButton(
                  onPressed: _openGenericCopilot,
                  backgroundColor: Colors.blue,
                  child: const Icon(Icons.assistant),
                )
              : null,

      body: Column(
        children: [
          _buildHeader(),
          const SizedBox(height: 12),

          if (_viewState != HomeViewState.detail &&
              _viewState != HomeViewState.copilotGeneric)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SearchBarWidget(onSearch: _onSearch),
            ),

          const SizedBox(height: 12),
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
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      color: Colors.blue,
      child: Row(
        children: [
          if (_viewState != HomeViewState.home)
            IconButton(
              icon: const Icon(Icons.arrow_back, color: Colors.white),
              onPressed: _handleBack,
            ),
          Expanded(
            child: Text(
              _viewState == HomeViewState.copilotGeneric
                  ? "Product Copilot"
                  : "Product Discovery Portal",
              style: const TextStyle(
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
  // BODY
  // --------------------------------------------------
  Widget _buildBody() {
    switch (_viewState) {
      case HomeViewState.copilotGeneric:
        // ✅ GENERIC COPILOT (NO PRODUCT ID)
        return const CopilotChatView();

      case HomeViewState.home:
        return const SizedBox.shrink();

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
  // SEARCH RESULTS
  // --------------------------------------------------
  Widget _buildSearchResults() {
    return FutureBuilder<List<Product>>(
      future: _searchFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        final products = snapshot.data ?? [];
        if (products.isEmpty) {
          return const Center(child: Text("No products found"));
        }

        return ListView.separated(
          itemCount: products.length,
          separatorBuilder: (_, __) =>
              const Divider(height: 1),
          itemBuilder: (_, i) {
            final product = products[i];
            final sellingPrice =
                product.price?['selling'];

            return ListTile(
        leading: product.images.isNotEmpty
      ? Image.network(
          "http://localhost:8000/image-proxy?"
          "url=${Uri.encodeComponent(product.images.first)}",
          width: 60,
          fit: BoxFit.cover,
        )
      : const Icon(Icons.image),

  title: Text(product.title, maxLines: 2),
  subtitle: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(product.brand ?? ""),
      if (product.price != null &&
          product.price!['selling'] != null)
        Text(
          "₹${product.price!['selling']}",
          style: const TextStyle(
            fontWeight: FontWeight.bold,
          ),
        ),
    ],
  ),

  // ✅ PRODUCT‑SPECIFIC COPILOT BUTTON
  trailing: IconButton(
    icon: const Icon(
      Icons.assistant,
      color: Colors.blue,
    ),
    tooltip: "Ask Copilot",
    onPressed: () {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => CopilotChatView(
            productId: product.pid,
          ),
        ),
      );
    },
  ),

  onTap: () => _openProduct(product.pid),
            );
          },
        );
      },
    );
  }
}