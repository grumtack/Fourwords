#!/usr/bin/env python3
import sys
import os
import re
import random
import argparse
from pathlib import Path

def extract_vocabulary_from_usfm(file_path):
    """Extract vocabulary from a USFM file, preserving capitalization patterns."""
    vocabulary = {}
    
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Remove USFM tags but keep the text
    # This regex matches USFM tags like \v 1, \p, \q1, etc.
    text_only = re.sub(r'\\[a-zA-Z]+[0-9]*\s*(?:\d+\s*)?', ' ', content)
    
    # Split into sentences to help identify sentence-starting words
    sentences = re.split(r'[.!?]+', text_only)
    
    for sentence in sentences:
        # Find all words in the sentence
        words = re.findall(r'\b[a-zA-Z]+\b', sentence.strip())
        
        for i, word in enumerate(words):
            word_lower = word.lower()
            
            # Determine if this word should preserve capitalization
            preserve_caps = False
            
            # Always preserve if it's a proper noun (starts with capital and not first word)
            if word[0].isupper() and i > 0:
                preserve_caps = True
            # Also preserve if it's all caps (acronym)
            elif word.isupper() and len(word) > 1:
                preserve_caps = True
            
            # Store the word with its capitalization pattern
            if word_lower not in vocabulary:
                vocabulary[word_lower] = {
                    'original': word if preserve_caps else word_lower,
                    'preserve_caps': preserve_caps,
                    'count': 1
                }
            else:
                vocabulary[word_lower]['count'] += 1
                # If we see a capitalized version that's not sentence-initial, preserve it
                if preserve_caps and not vocabulary[word_lower]['preserve_caps']:
                    vocabulary[word_lower]['original'] = word
                    vocabulary[word_lower]['preserve_caps'] = True
    
    return vocabulary

def generate_unique_nonsense_words(chars, num_words):
    """Generate unique 4-letter nonsense words from given characters."""
    # Clean the character input - remove brackets if present
    if chars.startswith('[') and chars.endswith(']'):
        chars = chars[1:-1]
    
    char_list = list(chars)
    words = set()
    
    # Ensure we can generate enough unique words
    max_possible = len(char_list) ** 4
    if num_words > max_possible:
        print(f"Warning: Requested {num_words} words but only {max_possible} unique combinations possible")
        num_words = max_possible
    
    while len(words) < num_words:
        word = ''.join(random.choice(char_list) for _ in range(4))
        words.add(word)
    
    return list(words)

def create_lexicon(vocabulary, nonsense_words):
    """Create a lexicon mapping real words to nonsense words."""
    lexicon = {}
    vocab_items = list(vocabulary.items())
    
    # Sort by frequency (most common words get consistent nonsense words)
    vocab_items.sort(key=lambda x: x[1]['count'], reverse=True)
    
    for i, (word_lower, word_info) in enumerate(vocab_items):
        if i < len(nonsense_words):
            lexicon[word_lower] = nonsense_words[i]
        else:
            # If we run out of nonsense words, generate more
            additional_word = ''.join(random.choice(list(nonsense_words[0])) for _ in range(4))
            lexicon[word_lower] = additional_word
    
    return lexicon

def transform_usfm_content(content, lexicon, vocabulary):
    """Transform USFM content using the lexicon while preserving formatting."""
    def replace_word(match):
        word = match.group(0)
        word_lower = word.lower()
        
        # Check if this word is part of an \id tag
        start_pos = match.start()
        # Look backwards to see if we're in an \id tag
        preceding_text = content[:start_pos]
        
        # Find the last \id tag before this position
        id_matches = list(re.finditer(r'\\id\s+', preceding_text))
        if id_matches:
            last_id_match = id_matches[-1]
            # Check if there's a newline between the \id tag and current word
            text_after_id = preceding_text[last_id_match.end():]
            if '\n' not in text_after_id:
                # We're still on the same line as \id, so preserve this word
                return word
        
        if word_lower in lexicon:
            replacement = lexicon[word_lower]
            
            # Apply original capitalization pattern
            if word_lower in vocabulary and vocabulary[word_lower]['preserve_caps']:
                # Use the preserved capitalization pattern
                original = vocabulary[word_lower]['original']
                if original[0].isupper():
                    replacement = replacement.capitalize()
                if original.isupper():
                    replacement = replacement.upper()
            elif word[0].isupper():
                replacement = replacement.capitalize()
            elif word.isupper():
                replacement = replacement.upper()
            
            return replacement
        
        return word
    
    # Replace words while preserving USFM tags and punctuation
    # This regex finds words (letters only) that are not part of USFM tags
    result = re.sub(r'(?<!\\[a-zA-Z])\b[a-zA-Z]+\b', replace_word, content)
    
    # Clean up \id lines - keep only the book code, remove everything after
    result = re.sub(r'\\id\s+([A-Z0-9]+).*', r'\\id \1', result)
    
    # Ensure proper spacing around punctuation
    # Add space before punctuation if there isn't one
    result = re.sub(r'(\w)([.!?;:,])', r'\1 \2', result)
    # Add space after punctuation if there isn't one (but not at end of line)
    result = re.sub(r'([.!?;:,])(\w)', r'\1 \2', result)
    
    # Add space after quotes
    result = re.sub(r'"(\w)', r'" \1', result)
    
    # Add space before backslash that comes immediately after a word
    result = re.sub(r'(\w)\\', r'\1 \\', result)
    
    return result

def process_usfm_directory(input_dir, output_dir, chars):
    """Process all USFM files in a directory."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory
    output_path.mkdir(exist_ok=True)
    
    # Find all USFM files
    usfm_files = list(input_path.glob('*.usfm')) + list(input_path.glob('*.SFM'))
    
    if not usfm_files:
        print(f"No USFM files found in {input_dir}")
        return
    
    print(f"Found {len(usfm_files)} USFM files")
    
    # Extract vocabulary from all files
    all_vocabulary = {}
    for usfm_file in usfm_files:
        print(f"Extracting vocabulary from {usfm_file.name}...")
        file_vocab = extract_vocabulary_from_usfm(usfm_file)
        
        # Merge vocabularies
        for word_lower, word_info in file_vocab.items():
            if word_lower in all_vocabulary:
                all_vocabulary[word_lower]['count'] += word_info['count']
                # Preserve caps if either instance suggests it
                if word_info['preserve_caps'] and not all_vocabulary[word_lower]['preserve_caps']:
                    all_vocabulary[word_lower]['original'] = word_info['original']
                    all_vocabulary[word_lower]['preserve_caps'] = True
            else:
                all_vocabulary[word_lower] = word_info.copy()
    
    print(f"Total unique words found: {len(all_vocabulary)}")
    
    # Generate nonsense words
    print("Generating nonsense words...")
    nonsense_words = generate_unique_nonsense_words(chars, len(all_vocabulary))
    
    # Create lexicon
    print("Creating lexicon...")
    lexicon = create_lexicon(all_vocabulary, nonsense_words)
    
    # Save lexicon to file
    lexicon_file = output_path / 'lexicon.txt'
    with open(lexicon_file, 'w', encoding='utf-8') as f:
        for real_word, nonsense_word in sorted(lexicon.items()):
            f.write(f"{real_word}\t{nonsense_word}\n")
    print(f"Lexicon saved to {lexicon_file}")
    
    # Transform each USFM file
    for usfm_file in usfm_files:
        print(f"Transforming {usfm_file.name}...")
        
        with open(usfm_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        transformed_content = transform_usfm_content(content, lexicon, all_vocabulary)
        
        # Write transformed file
        output_file = output_path / usfm_file.name
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(transformed_content)
    
    print(f"All files transformed and saved to {output_dir}")

def main():
    parser = argparse.ArgumentParser(
        description="Transform USFM files by replacing words with nonsense words while preserving formatting."
    )
    parser.add_argument("input_dir", help="Directory containing USFM files")
    parser.add_argument("chars", help="Characters to use for generating nonsense words")
    parser.add_argument("-o", "--output", default="FourUSFM", 
                       help="Output directory name (default: FourSFM)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        sys.exit(1)
    
    if not os.path.isdir(args.input_dir):
        print(f"Error: '{args.input_dir}' is not a directory")
        sys.exit(1)
    
    print(f"Processing USFM files from: {args.input_dir}")
    print(f"Using characters: {args.chars}")
    print(f"Output directory: {args.output}")
    
    process_usfm_directory(args.input_dir, args.output, args.chars)

if __name__ == "__main__":
    main()
