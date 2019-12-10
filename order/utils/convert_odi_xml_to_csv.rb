
fail 'path for xml file' if ARGV.size == 0

require 'rexml/document'
require 'rexml/document'

file = File.open(ARGV.first)


doc = REXML::Document.new(file)
products = REXML::XPath.match(doc, '//product')

text_fields = ['bestelnummer', 'omschrijving', 'btw', 'inhoud', 'kassaomschrijving', 'eenheid', 'merk', 'cblcode', 'sve', 'verpakkingce', 'status']
selected_columns = text_fields + ['inkoopprijs']

File.open('prods.csv', 'wb') do |tsv|
  tsv << selected_columns.join("\t")

  tsv << "\n"

  products.each do |product|
    row = text_fields.map { |field| product.elements[field].text }

    row << product.elements['prijs'].elements['inkoopprijs'].text
    tsv << row.join("\t")
    tsv << "\n"
  end
end
