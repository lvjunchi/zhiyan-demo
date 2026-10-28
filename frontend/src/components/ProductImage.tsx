import productImage from '../assets/fast-12js-product.png'

/** Original manufacturer product image, bundled locally for offline viewing. */
export function ProductImage() {
  // Trim only the source image's empty top margin in the viewport; preserve its original bytes.
  return <svg className="gearbox-art" viewBox="0 140 1626 944" role="img" aria-label="法士特 12JS 系列变速器产品参考图">
    <image href={productImage} width={1626} height={1084} />
  </svg>
}
