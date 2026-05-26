import 'package:flutter/material.dart';
import '../models/product.dart';
import '../services/product_service.dart';
import 'copilot_chat_view.dart';
import '../services/recommendation_service.dart';

class ProductDetailView extends StatefulWidget {
  final String productId;
  final String? query;
  final void Function(
  String productId, {
  bool fromSearch,
  bool fromSimilar,
}) onOpenProduct;





  const ProductDetailView({
    super.key,
    required this.productId,
    required this.onOpenProduct,
    this.query,
  });


  @override
  State<ProductDetailView> createState() => _ProductDetailViewState();
}

class _ProductDetailViewState extends State<ProductDetailView> {
  late Future<Product> _productFuture;
  late Future<List<Product>> _similarFuture;
  late Future<List<Product>> _alternativesFuture;

  @override
  void initState() {
    super.initState();
    _load(widget.productId);
  }

  @override
  void didUpdateWidget(covariant ProductDetailView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.productId != widget.productId) {
      _load(widget.productId);
    }
  }

  void _load(String id) {
    _productFuture = ProductService.fetchProductById(id);
    _similarFuture = ProductService.fetchSimilarProducts(id);

    // ✅ NEW: Alternatives
    _alternativesFuture =
        RecommendationService.getNextBestAlternatives(
          productId: id
        );
  }

  String _price(Product p) =>
      p.price is Map && p.price['selling'] != null
          ? "₹${p.price['selling']}"
          : "N/A";

  void _openCopilot(String pid) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CopilotChatView(productId: pid),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Product>(
      future: _productFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }

        final product = snapshot.data!;

        return Scaffold(
          backgroundColor: Colors.white,
          floatingActionButton: FloatingActionButton.extended(
            onPressed: () => _openCopilot(product.pid),
            label: const Text("Ask Copilot"),
            icon: const Icon(Icons.assistant),
            backgroundColor : Colors.blue,
          ),
          body: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _imageSection(product.images),
                const SizedBox(height: 16),
                Text(product.title,
                    style: const TextStyle(
                        fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text(product.brand ?? "",
                    style: TextStyle(color: Colors.grey.shade600)),
                const SizedBox(height: 8),
                Text(_price(product),
                    style: const TextStyle(
                        fontSize: 22, fontWeight: FontWeight.bold)),
                const Divider(height: 32),
                const Text("Description",
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                Text(product.description.isNotEmpty
                    ? product.description
                    : "No description available"),
                const Divider(height: 32),
                const Text("Specifications",
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                _specs(product.specifications),
                const Divider(height: 32),
                const Text("Similar Products",
                    style:
                        TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                const SizedBox(height: 12),
                _similarProducts(),
                const Divider(height: 32),
                const Text(
                  "Next Best Alternatives",
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                const SizedBox(height: 12),
                _alternativeProducts(),
              ],
            ),
          ),
        );
      },
    );
  }

  // ---------------- IMAGE ----------------
  Widget _imageSection(List<String> images) {
    return SizedBox(
      height: 220,
      child: images.isEmpty
          ? Container(color: Colors.grey.shade200)
          : PageView(
              children: images
                  .map((e) => Image.network(
                        _proxy(e),
                        fit: BoxFit.contain,
                      ))
                  .toList(),
            ),
    );
  }

  // ---------------- SPECS ----------------
  Widget _specs(dynamic specs) {
    if (specs == null ||
        specs is! Map ||
        !specs.containsKey('product_specification')) {
      return const Text("No specifications");
    }

    final List list = specs['product_specification'];
    return Column(
      children: list
          .map(
            (s) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Expanded(
                      flex: 4,
                      child: Text(s['key'],
                          style: const TextStyle(
                              fontWeight: FontWeight.w600))),
                  Expanded(flex: 6, child: Text(s['value'])),
                ],
              ),
            ),
          )
          .toList(),
    );
  }

  // ---------------- ✅ SIMILAR PRODUCTS (FIXED) ----------------
  Widget _similarProducts() {
    const double cardWidth = 180;
    const double cardHeight = cardWidth / 0.78;

    return FutureBuilder<List<Product>>(
      future: _similarFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const Text("No similar products",
              style: TextStyle(color: Colors.grey));
        }

        final products = snapshot.data!;

        return SizedBox(
          height: cardHeight,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: products.length,
            separatorBuilder: (_, __) => const SizedBox(width: 16),
            itemBuilder: (_, i) =>
                SizedBox(
                    width: cardWidth,
                    height: cardHeight,
                    child: _similarCard(products[i])),
          ),
        );
      },
    );
  }

  // ---------------- ✅ COMPACT CARD ----------------
  Widget _similarCard(Product p) {
  return Material(
    color: Colors.white,
    borderRadius: BorderRadius.circular(16),
    elevation: 1.5,
    child: InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: () => widget.onOpenProduct(
        p.pid,
        fromSimilar: true, // ✅ Similar product click
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              height: 110,
              width: double.infinity,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: p.images.isNotEmpty
                    ? Image.network(
                        _proxy(p.images.first),
                        fit: BoxFit.contain,
                      )
                    : const Icon(Icons.image, size: 32),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              p.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              p.brand ?? "",
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade700,
              ),
            ),
            const SizedBox(height: 6),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  _price(p),
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                InkWell(
                  onTap: () => _openCopilot(p.pid),
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
    ),
  );
}
  Widget _alternativeProducts() {
    const double cardWidth = 180;
    const double cardHeight = cardWidth / 0.78;

    return FutureBuilder<List<Product>>(
      future: _alternativesFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const Text(
            "No better alternatives found",
            style: TextStyle(color: Colors.grey),
          );
        }

        final products = snapshot.data!;

        return SizedBox(
          height: cardHeight,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: products.length,
            separatorBuilder: (_, __) => const SizedBox(width: 16),
            itemBuilder: (_, i) => SizedBox(
              width: cardWidth,
              child: _alternativeCard(products[i]),
            ),
          ),
        );
      },
    );
  }

  Widget _alternativeCard(Product p) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      elevation: 2,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => widget.onOpenProduct(
          p.pid,
          fromSimilar: true,
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                height: 110,
                width: double.infinity,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: p.images.isNotEmpty
                      ? Image.network(
                    _proxy(p.images.first),
                    fit: BoxFit.contain,
                  )
                      : const Icon(Icons.image, size: 32),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                p.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                p.brand ?? "",
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey.shade700,
                ),
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    _price(p),
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  InkWell(
                    onTap: () => _openCopilot(p.pid),
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: Colors.blue, // ✅ differentiate
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
      ),
    );
  }

  String _proxy(String url) {
    return "http://10.0.2.2:8000/image-proxy?url=${Uri.encodeComponent(url)}";
  }
}