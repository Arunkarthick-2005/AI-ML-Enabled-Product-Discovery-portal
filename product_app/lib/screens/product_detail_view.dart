import 'package:flutter/material.dart';
import '../models/product.dart';
import '../services/product_service.dart';
import 'copilot_chat_view.dart';

class ProductDetailView extends StatefulWidget {
  final String productId;

  /// ✅ CALLBACK TO OPEN ANOTHER PRODUCT
  final void Function(String productId) onOpenProduct;

  const ProductDetailView({
    super.key,
    required this.productId,
    required this.onOpenProduct,
  });

  @override
  State<ProductDetailView> createState() => _ProductDetailViewState();
}

class _ProductDetailViewState extends State<ProductDetailView> {
  late Future<Product> _productFuture;
  late Future<List<Product>> _similarFuture;

  @override
  void initState() {
    super.initState();
    _loadData(widget.productId);
  }

  @override
  void didUpdateWidget(covariant ProductDetailView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.productId != widget.productId) {
      _loadData(widget.productId);
    }
  }

  void _loadData(String productId) {
    _productFuture = ProductService.fetchProductById(productId);
    _similarFuture = ProductService.fetchSimilarProducts(productId);
  }

  // -------------------------------------------------
  // ✅ SELLING PRICE HELPER (matches DB schema)
  // -------------------------------------------------
  String _sellingPrice(Product product) {
    final price = product.price;
    if (price is Map<String, dynamic> && price['selling'] != null) {
      return "₹${price['selling']}";
    }
    return "N/A";
  }

  // -------------------------------------------------
  // ✅ OPEN PRODUCT‑SCOPED COPILOT
  // -------------------------------------------------
  void _openProductCopilot(String productId) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CopilotChatView(productId: productId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Product>(
      future: _productFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        if (snapshot.hasError || !snapshot.hasData) {
          return const Center(child: Text("Failed to load product"));
        }

        return _buildProductUI(snapshot.data!);
      },
    );
  }

  // -------------------------------------------------
  // PRODUCT UI
  // -------------------------------------------------
  Widget _buildProductUI(Product product) {
    return Scaffold(
      backgroundColor: Colors.white,

      // ✅ PRODUCT‑LEVEL COPILOT BUTTON
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openProductCopilot(product.pid),
        icon: const Icon(Icons.assistant),
        label: const Text("Ask Copilot"),
        backgroundColor: Colors.blue,
      ),

      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _imageSection(product.images),

            const SizedBox(height: 16),

            Text(
              product.title,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),

            const SizedBox(height: 6),

            Text(
              product.brand ?? "N/A",
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade600,
              ),
            ),

            const SizedBox(height: 10),

            Text(
              _sellingPrice(product),
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: Colors.black,
              ),
            ),

            const Divider(height: 32),

            const Text(
              "Description",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            Text(
              product.description.isNotEmpty
                  ? product.description
                  : "No description available",
            ),

            const Divider(height: 32),

            const Text(
              "Specifications",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            _buildSpecifications(product.specifications),

            const Divider(height: 32),

            const Text(
              "Similar Products",
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
            const SizedBox(height: 12),

            _buildSimilarProducts(),
          ],
        ),
      ),
    );
  }

  // -------------------------------------------------
  // IMAGE SECTION
  // -------------------------------------------------
  Widget _imageSection(List<String> images) {
    if (images.isEmpty) {
      return Container(
        height: 220,
        color: Colors.grey.shade200,
        alignment: Alignment.center,
        child: const Text("No Image"),
      );
    }

    return SizedBox(
      height: 220,
      child: PageView.builder(
        itemCount: images.length,
        itemBuilder: (_, index) {
          return Image.network(
            _proxyImageUrl(images[index]),
            fit: BoxFit.contain,
          );
        },
      ),
    );
  }

  // -------------------------------------------------
  // SPECIFICATIONS
  // -------------------------------------------------
  Widget _buildSpecifications(dynamic specs) {
    if (specs == null ||
        specs is! Map ||
        !specs.containsKey('product_specification')) {
      return const Text("No specifications available");
    }

    final List list = specs['product_specification'];

    return Column(
      children: list.map((s) {
        final key = s['key'] ?? '';
        final value = s['value'] ?? '';
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            children: [
              Expanded(
                flex: 4,
                child: Text(
                  key,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              Expanded(flex: 6, child: Text(value)),
            ],
          ),
        );
      }).toList(),
    );
  }

  // -------------------------------------------------
  // ✅ SIMILAR PRODUCTS (WITH PRICE + COPILOT)
  // -------------------------------------------------
  Widget _buildSimilarProducts() {
    return FutureBuilder<List<Product>>(
      future: _similarFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const Text(
            "No similar products found",
            style: TextStyle(color: Colors.grey),
          );
        }

        final products = snapshot.data!;

        return SizedBox(
          height: 260,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: products.length,
            itemBuilder: (context, index) {
              final p = products[index];

              return SizedBox(
                width: 180,
                child: Card(
                  margin: const EdgeInsets.only(right: 10),
                  child: InkWell(
                    onTap: () => widget.onOpenProduct(p.pid),
                    child: Padding(
                      padding: const EdgeInsets.all(8),
                      child: Column(
                        crossAxisAlignment:
                            CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: p.images.isNotEmpty
                                ? Image.network(
                                    _proxyImageUrl(p.images.first),
                                    fit: BoxFit.cover,
                                    width: double.infinity,
                                  )
                                : Container(
                                    color: Colors.grey.shade200,
                                    alignment: Alignment.center,
                                    child: const Icon(Icons.image),
                                  ),
                          ),

                          const SizedBox(height: 6),

                          Text(
                            p.title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 13),
                          ),

                          const SizedBox(height: 4),

                          Text(
                            p.brand ?? "N/A",
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.grey.shade600,
                            ),
                          ),

                          const SizedBox(height: 4),

                          Text(
                            _sellingPrice(p),
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                            ),
                          ),

                          Align(
                            alignment: Alignment.centerRight,
                            child: IconButton(
                              icon: const Icon(
                                Icons.assistant,
                                size: 18,
                                color: Colors.blue,
                              ),
                              tooltip: "Ask Copilot",
                              onPressed: () =>
                                  _openProductCopilot(p.pid),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        );
      },
    );
  }

  String _proxyImageUrl(String url) {
    return "http://localhost:8000/image-proxy?"
        "url=${Uri.encodeComponent(url)}";
  }
}